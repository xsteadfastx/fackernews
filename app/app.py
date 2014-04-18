import datetime
from flask import Flask, render_template, redirect, session, flash
from flask.ext.sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_wtf import Form, RecaptchaField
from sqlalchemy import desc
from wtforms import TextField, TextAreaField
from wtforms.validators import Required, URL, Email, Optional


exec(open('fackernews.conf').read())


app = Flask(__name__)
app.secret_key = SECRETKEY
app.config['SITENAME'] = SITENAME
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
app.config['RECAPTCHA_PUBLIC_KEY'] = RECAPTCHA_PUBLIC_KEY
app.config['RECAPTCHA_PRIVATE_KEY'] = RECAPTCHA_PRIVATE_KEY
db = SQLAlchemy(app)
Bootstrap(app)


def comment_counter(links):
    counter = []
    for link in links:
        counter.append(len(Comment.query.filter_by(link_id=link.id).all()))

    return counter


class Link(db.Model):
    ''' sqlalchemy stuff magic '''
    id = db.Column(db.Integer(), primary_key=True)
    url = db.Column(db.String())
    titel = db.Column(db.String())
    date_time = db.Column(db.DateTime())
    last_activity = db.Column(db.DateTime())
    upvotes = db.Column(db.Integer())

    comments = db.relationship('Comment',
                               backref='link', lazy='dynamic')

    def __init__(self, url, titel, date_time, last_activity, upvotes):
            self.url = url
            self.titel = titel
            self.date_time = date_time
            self.last_activity = last_activity
            self.upvotes = upvotes

    def __repr__(self):
            return '<Link(%r, %r, %r, %r, %r)>' % (self.url,
                                                   self.titel,
                                                   self.date_time,
                                                   self.last_activity,
                                                   self.upvotes)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String())
    email = db.Column(db.String())
    website = db.Column(db.String())
    message = db.Column(db.Text())
    date_time = db.Column(db.DateTime())
    upvotes = db.Column(db.Integer())

    link_id = db.Column(db.Integer, db.ForeignKey('link.id'))

    def __init__(self, name, email, website,
                 message, date_time, upvotes, link_id):
        self.name = name
        self.email = email
        self.website = website
        self.message = message
        self.date_time = date_time
        self.upvotes = upvotes
        self.link_id = link_id

    def __repr__(self):
        return '<Comment(%r, %r, %r, %r, %r, %r)>' % (self.name,
                                                      self.email,
                                                      self.website,
                                                      self.message,
                                                      self.date_time,
                                                      self.upvotes)


class LinkForm(Form):
    url = TextField('URL', validators=[Required(), URL()])
    titel = TextField('Titel', validators=[Required()])
    recaptcha = RecaptchaField()


class CommentForm(Form):
    name = TextField('Name', validators=[Required()])
    email = TextField('Email', validators=[Required(), Email()])
    website = TextField('Website', validators=[Optional(), URL()])
    message = TextAreaField('Message', validators=[Required()])
    recaptcha = RecaptchaField()


@app.route('/')
def index():
    ''' frontpage '''
    twenty_four_hours_ago = datetime.datetime.utcnow(
        ) - datetime.timedelta(hours=HOURS_TO_LIVE_FRONTPAGE)
    links = Link.query.filter(
        Link.last_activity > twenty_four_hours_ago).order_by(
        desc(Link.upvotes)).limit(30)

    counter = comment_counter(links)

    if 'voted' not in session:
            session['voted'] = []

    return render_template('index.html',
                           links=enumerate(links),
                           counter=counter)


@app.route('/new')
def new():
    ''' lists new links without ordering them '''
    twenty_four_hours_ago = datetime.datetime.utcnow(
        ) - datetime.timedelta(hours=HOURS_TO_LIVE_NEW)
    links = Link.query.filter(
        Link.date_time > twenty_four_hours_ago).order_by(
        desc(Link.date_time)).limit(30)

    counter = comment_counter(links)

    return render_template('index.html',
                           links=enumerate(links),
                           counter=counter)


@app.route('/submit', methods=('GET', 'POST'))
def submit():
    ''' adding new link '''
    form = LinkForm()
    if form.validate_on_submit():
        link = Link(form.url.data,
                    form.titel.data,
                    datetime.datetime.utcnow(),
                    datetime.datetime.utcnow(),
                    0)
        db.session.add(link)
        db.session.commit()

        flash('Added link')

        return redirect('/')

    return render_template('submit.html', form=form)


@app.route('/upvote/<int:link_id>')
def upvote(link_id):
    ''' upvotes a link and doing some session stuff '''
    link = Link.query.filter_by(id=link_id).first()
    link.upvotes += 1
    link.last_activity = datetime.datetime.utcnow()
    db.session.commit()

    if 'voted_links' in session:
        session['voted_links'].append(str(link_id))
    else:
        session['voted_links'] = []

    return redirect('/')


@app.route('/comments/<int:link_id>', methods=('GET', 'POST'))
def comments(link_id):
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(form.name.data,
                          form.email.data,
                          form.website.data,
                          form.message.data,
                          datetime.datetime.utcnow(),
                          0,
                          link_id)
        db.session.add(comment)
        link = Link.query.filter_by(id=link_id).first()
        link.last_activity = datetime.datetime.utcnow()
        db.session.commit()

        flash('Added comment')

        return redirect('/comments/' + str(link_id))

    titel = Link.query.filter_by(id=link_id).first().titel

    comments = Comment.query.filter_by(link_id=link_id).order_by(desc(Comment.upvotes)).all()

    return render_template('comments.html',
                           link_id=link_id,
                           form=form,
                           titel=titel,
                           comments=comments)


@app.route('/comments/<int:link_id>/upvote/<int:comment_id>')
def comment_upvote(link_id, comment_id):
    comment = Comment.query.filter_by(id=comment_id).first()
    comment.upvotes += 1
    link = Link.query.filter_by(id=link_id).first()
    link.last_activity = datetime.datetime.utcnow()
    db.session.commit()

    if 'voted_comments' in session:
        session['voted_comments'].append(str(comment_id))
    else:
        session['voted_comments'] = []

    return redirect('/comments/' + str(link_id))


if __name__ == '__main__':
    app.run(debug=True)
