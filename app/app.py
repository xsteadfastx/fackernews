import bson
import datetime
from flask import Flask, render_template, redirect, session, flash, request
from flask.ext.mongoengine import MongoEngine
from flask_bootstrap import Bootstrap
from flask_wtf import Form, RecaptchaField
from urllib.parse import urljoin, urlparse
from werkzeug.contrib.atom import AtomFeed
from wtforms import TextField, TextAreaField
from wtforms.validators import Required, URL, Optional


exec(open('fackernews.conf').read())


app = Flask(__name__)
app.secret_key = SECRETKEY
app.config['SITENAME'] = SITENAME
app.config['MONGODB_SETTINGS'] = MONGODB_SETTINGS
app.config['RECAPTCHA_PUBLIC_KEY'] = RECAPTCHA_PUBLIC_KEY
app.config['RECAPTCHA_PRIVATE_KEY'] = RECAPTCHA_PRIVATE_KEY
db = MongoEngine(app)
Bootstrap(app)


def comment_counter(links):
    counter = []
    for link in links:
        counter.append(len(link.comments))

    return counter


def make_external(url):
    return urljoin(request.url_root, url)


class Link(db.Document):
    ''' mongo magic '''
    titel = db.StringField(max_length=255, required=True)
    url = db.StringField(max_length=255)
    text = db.StringField()
    created_at = db.DateTimeField(
        default=datetime.datetime.utcnow(), required=True)
    last_activity = db.DateTimeField(
        default=datetime.datetime.utcnow(), required=True)
    upvotes = db.IntField()
    comments = db.SortedListField(db.EmbeddedDocumentField('Comment'),
                                  ordering='upvotes', reverse=True)

    meta = {'allow_inheritance': True,
            'indexes': ['-created_at']}


class Comment(db.EmbeddedDocument):
    ''' mongo magic '''
    id = db.ObjectIdField(required=True, default=lambda: bson.ObjectId())
    name = db.StringField(verbose_name='Name', max_length=255, required=True)
    website = db.StringField(max_length=255)
    message = db.StringField(verbose_name='Comment', required=True)
    created_at = db.DateTimeField(
        default=datetime.datetime.utcnow(), required=True)
    upvotes = db.IntField()


class LinkForm(Form):
    titel = TextField('Titel', validators=[Required()])
    url = TextField('URL', validators=[URL(), Optional()])
    text = TextAreaField('Text')
    recaptcha = RecaptchaField()


class CommentForm(Form):
    name = TextField('Name', validators=[Required()])
    website = TextField('Website', validators=[Optional(), URL()])
    message = TextAreaField('Message', validators=[Required()])
    recaptcha = RecaptchaField()


@app.route('/')
def index():
    ''' frontpage '''
    hours_ago = datetime.datetime.utcnow(
        ) - datetime.timedelta(hours=HOURS_TO_LIVE_FRONTPAGE)

    links = Link.objects(last_activity__gt=hours_ago).order_by('-upvotes')[:30]

    link_hostnames = []
    for link in links:
        if link.url:
            link_hostnames.append(urlparse(link.url).hostname)
        else:
            link_hostnames.append(
                urlparse(make_external(
                    'comments/%s' % str(link.id))).hostname)

    counter = comment_counter(links)

    if 'voted' not in session:
            session['voted'] = []

    return render_template('index.html',
                           links=enumerate(links),
                           link_hostnames=link_hostnames,
                           counter=counter)


@app.route('/index.atom')
def index_atom():
    ''' feed for the frontpage '''
    feed = AtomFeed(SITENAME,
                    feed_url=request.url, url=request.url_root)

    hours_ago = datetime.datetime.utcnow(
        ) - datetime.timedelta(hours=HOURS_TO_LIVE_FRONTPAGE)

    links = Link.objects(last_activity__gt=hours_ago).order_by('-upvotes')[:30]

    for link in links:
        feed.add(link.titel,
                 content_type='html',
                 author=SITENAME,
                 url=make_external('comments/%s' % str(link.id)),
                 updated=link.created_at)

    return feed.get_response()


@app.route('/new')
def new():
    ''' lists new links without ordering them '''
    hours_ago = datetime.datetime.utcnow(
        ) - datetime.timedelta(hours=HOURS_TO_LIVE_NEW)

    links = Link.objects(
        last_activity__gt=hours_ago).order_by('-created_at')[:30]

    link_hostnames = []
    for link in links:
        if link.url:
            link_hostnames.append(urlparse(link.url).hostname)
        else:
            link_hostnames.append(
                urlparse(make_external('comments/%s' % str(link.id))).hostname)

    counter = comment_counter(links)

    return render_template('index.html',
                           links=enumerate(links),
                           link_hostnames=link_hostnames,
                           counter=counter)


@app.route('/new.atom')
def new_atom():
    ''' feed for the new links '''
    feed = AtomFeed('Recent Links',
                    feed_url=request.url, url=request.url_root)

    hours_ago = datetime.datetime.utcnow(
        ) - datetime.timedelta(hours=HOURS_TO_LIVE_NEW)

    links = Link.objects(
        last_activity__gt=hours_ago).order_by('-created_at')[:30]

    for link in links:
        feed.add(link.titel,
                 content_type='html',
                 author=SITENAME,
                 url=make_external('comments/%s' % str(link.id)),
                 updated=link.created_at)

    return feed.get_response()


@app.route('/submit', methods=('GET', 'POST'))
def submit():
    ''' adding new link '''
    # if there is data from a fail submit, prefill forms
    if 'submit_data' in session and session['submit_data']:
        data = session['submit_data']
        form = LinkForm(titel=data[0], url=data[1], text=data[2])
    else:
        form = LinkForm()
    if form.validate_on_submit():
        if bool(form.url.data) ^ bool(form.text.data):
            link = Link(titel=form.titel.data,
                        url=form.url.data,
                        text=form.text.data,
                        created_at=datetime.datetime.utcnow(),
                        last_activity=datetime.datetime.utcnow(),
                        upvotes=0)
            link.save()

            # append id to voted_links if its you who submitted the link
            if 'voted_links' in session:
                session['voted_links'].append(str(link.id))
            else:
                session['voted_links'] = []

            flash('Added link', 'success')
            session['submit_data'] = []

            return redirect('/submit')

        else:
            flash('Choose between URL or Text', 'danger')
            session['submit_data'] = [form.titel.data,
                                      form.url.data,
                                      form.text.data]

            return redirect('/submit')

    return render_template('submit.html', form=form)


@app.route('/upvote/<link_id>')
def upvote(link_id):
    ''' upvotes a link and doing some session stuff '''
    link = Link.objects(id=link_id).first()
    link.upvotes += 1
    link.last_activity = datetime.datetime.utcnow()
    link.save()

    if 'voted_links' in session:
        session['voted_links'].append(str(link_id))
    else:
        session['voted_links'] = []

    return redirect('/')


@app.route('/comments/<link_id>', methods=('GET', 'POST'))
def comments(link_id):
    form = CommentForm()
    link = Link.objects(id=link_id).first()
    if link.url:
        link_hostname = urlparse(link.url).hostname
    else:
        link_hostname = urlparse(
            make_external('comments/%s' % str(link.id))).hostname

    if form.validate_on_submit():
        link = Link.objects(id=link_id).first()
        comment = Comment(name=form.name.data,
                          website=form.website.data,
                          message=form.message.data,
                          created_at=datetime.datetime.utcnow(),
                          upvotes=0)
        link.comments.append(comment)
        link.last_activity = datetime.datetime.utcnow()
        link.save()

        # append id to voted_comments if its you who submitted the comment
        if 'voted_comments' in session:
            session['voted_comments'].append(str(comment.id))
        else:
            session['voted_comments'] = []

        flash('Added comment', 'success')

        return redirect('/comments/' + str(link_id))

    comments = link.comments

    return render_template('comments.html',
                           link=link,
                           link_hostname=link_hostname,
                           form=form,
                           comments=comments)


@app.route('/comments/<link_id>/upvote/<comment_id>')
def comment_upvote(link_id, comment_id):
    link = Link.objects(id=link_id).first()
    for i in link.comments:
        if str(comment_id) == str(i.id):
            i.upvotes += 1

    link.last_activity = datetime.datetime.utcnow()
    link.save()

    if 'voted_comments' in session:
        session['voted_comments'].append(str(comment_id))
    else:
        session['voted_comments'] = []

    return redirect('/comments/' + str(link_id))


if __name__ == '__main__':
    app.run(debug=True)
