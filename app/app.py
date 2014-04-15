import datetime
import os
from flask import Flask, render_template, redirect, session, request, flash
from flask_wtf import Form
from wtforms import TextField
from wtforms.validators import Required, URL
from flask.ext.sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from sqlalchemy import desc


app = Flask(__name__)
#app.secret_key = os.urandom(24)
app.secret_key = 'f00b4r'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
db = SQLAlchemy(app)
Bootstrap(app)


class Link(db.Model):
    ''' sqlalchemy stuff magic '''
    id = db.Column(db.Integer(), primary_key=True)
    url = db.Column(db.String())
    titel = db.Column(db.String())
    date_time = db.Column(db.DateTime())
    upvotes = db.Column(db.Integer())

    def __init__(self, url, titel, date_time, upvotes):
        self.url = url
        self.titel = titel
        self.date_time = date_time
        self.upvotes = upvotes

    def __repr__(self):
        return '<Link(%r, %r, %r, %r)>' % (self.url,
                                           self.titel,
                                           self.date_time,
                                           self.upvotes)


class LinkForm(Form):
    url = TextField('URL', validators=[Required(), URL()])
    titel = TextField('Titel', validators=[Required()])


@app.route('/')
def index():
    ''' landing page '''
    twenty_four_hours_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    links = Link.query.filter(Link.date_time > twenty_four_hours_ago).order_by(desc(Link.upvotes)).limit(30)

    if 'voted' not in session:
        session['voted'] = []

    return render_template('index.html', links=links)


@app.route('/new')
def new():
    ''' lists new links without ordering them '''
    links = Link.query.order_by(desc(Link.date_time))
    return render_template('index.html', links=links)


@app.route('/submit', methods=('GET', 'POST'))
def submit():
    ''' adding new link '''
    form = LinkForm()
    if form.validate_on_submit():
        link = Link(form.url.data,
                    form.titel.data,
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
    db.session.commit()

    if 'voted' in session:
        session['voted'].append(str(link_id))
    else:
        session['voted'] = []

    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
