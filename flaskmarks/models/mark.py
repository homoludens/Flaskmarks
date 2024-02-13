# flaskmarks/models/mark.py

from sqlalchemy import and_, or_, desc
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import Table
from sqlalchemy.ext.associationproxy import association_proxy
from datetime import datetime as dt
from ..core.setup import app, db, config
from .tag import Tag

from sqlalchemy.dialects.mysql import LONGTEXT

from sqlalchemy import event
from sqlalchemy.schema import DDL

from sqlalchemy_fulltext import FullText, FullTextSearch
import sqlalchemy_fulltext.modes as FullTextMode

# flask_whooshalchemy
#import flask_msearch
# from flask_msearch import Search
# search = Search(db=db)
# search.init_app(app)

from flask_whooshee import Whooshee
whooshee = Whooshee(app)
# Mark.query.whooshee_search('ferrari').all()

# search.update_index()


ass_tbl = db.Table('marks_tags', db.metadata,
                   db.Column('left_id', db.Integer, db.ForeignKey('marks.id')),
                   db.Column('right_id', db.Integer, db.ForeignKey('tags.id'))
                   )

# @whooshee.register_model('title', 'description', 'full_html')
class Mark(FullText, db.Model):
    __tablename__ = 'marks'
    # __searchable__ = ['title', 'description', 'full_html']
    __fulltext_columns__ = ('title', 'description', 'full_html', 'url')

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    type = db.Column(db.Unicode(255), nullable=False)
    title = db.Column(db.Unicode(255), nullable=False)
    description = db.Column(LONGTEXT, nullable=True)
    full_html = db.Column(LONGTEXT, nullable=True)
    url = db.Column(db.Unicode(512), nullable=False)
    clicks = db.Column(db.Integer, default=0)
    last_clicked = db.Column(db.DateTime)
    created = db.Column(db.DateTime)
    updated = db.Column(db.DateTime)

    tags = relationship('Tag',
                        secondary=ass_tbl,
                        lazy='joined',
                        backref='marks')

    valid_types = ['bookmark', 'feed', 'youtube']
    valid_feed_types = ['feed', 'youtube']

    def __init__(self, owner_id, created=False):
        self.owner_id = owner_id
        if created:
            self.created = created
        else:
            self.created = dt.utcnow()

    def insert_from_import(self, data):
        self.title = data['title']
        self.type = data['type']
        """ try to catch the wrongfully placed youtube feeds"""
        if 'gdata.youtube.com' in data['url']:
            self.type = 'youtube'
        self.url = data['url']
        self.clicks = data['clicks']
        self.created = dt.fromtimestamp(int(data['created']))

        if data['updated']:
            self.updated = dt.fromtimestamp(int(data['updated']))
        if data['last_clicked']:
            self.last_clicked = dt.fromtimestamp(int(data['last_clicked']))

        """ TAGS """
        tags = []
        for t in data['tags']:
            tag = Tag.check(t.lower())
            if not tag:
                tag = Tag(t.lower())
                db.session.add(tag)
            tags.append(tag)
        self.tags = tags

    def __repr__(self):
        return '<Mark %r>' % (self.title)


@event.listens_for(Mark, 'before_insert')
def receive_after_insert(self, db_connection, db_mark_object):
    pass
    # print(db_connection)
    # print(db_mark_object)
    # print("****************** receive_after_insert ****************")

@event.listens_for(Mark.__table__, 'after_create')
def receive_after_create(self, db_connection, db_mark_object):
    print(db_connection)
    print(db_mark_object)
    add_full_text_search_sql = """
        ALTER TABLE marks \
        ADD FULLTEXT INDEX `fulltext_marks` \
        (`title`, `description`, `full_html`, `url`)
    """


# https://stackoverflow.com/questions/36455599/alembic-flask-migrate-not-detecting-after-create-events
# https://stackoverflow.com/questions/76640875/how-to-use-mysql-fulltext-search-index-and-match-against-in-sqlalchemy-orm
