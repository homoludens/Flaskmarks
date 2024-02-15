import threading
from flask.globals import _request_ctx_stack
from flask import (
    Blueprint,
    render_template,
    flash,
    redirect,
    url_for,
    g,
    request,
    abort,
    jsonify,
    json,
    current_app
)
from flask_login import login_user, logout_user, login_required
from werkzeug.utils import secure_filename
import os
# from bs4 import BeautifulSoup as BSoup
from readability.readability import Document
from urllib.request import urlopen
from datetime import datetime
from urllib.parse import urlparse, urljoin
import feedparser
from typing import Iterable
from newspaper import Article, ArticleBinaryDataException
#from gensim.summarization import keywords
from werkzeug.utils import secure_filename
import tldextract
import requests
from ..core.setup import app, db
from ..core.youtube import get_youtube_info, check_url_video
from ..core.error import is_safe_url
from threading import Thread
from ..models import Mark
from ..models.tag import Tag


class MarksImportThread(Thread):
    # constructor
    def __init__(self, url, user_id):
        # execute the base constructor
        Thread.__init__(self)
        # set a default value
        self.url = url
        self.user_id = user_id
        self.m = None
 
    # function executed in a new thread
    def run(self):

        url = self.url

        print(f"Total Active threads are {threading.activeCount()}")
        print(f"new_imported_mark_thread: {url}")
        
        url_domain = tldextract.extract(url).domain
        readable_title = None

        m = {}
        m['type'] = 'bookmark'
        m['tags'] = []

        m['url'] = url
        m['title'] = url
        m['description'] = ''
        m['full_html'] = ''
        
        if url_domain in ['youtube', 'youtu'] and check_url_video(url):
            print(url_domain)
            youtube_info_dict = get_youtube_info(url)
            m['title'] = youtube_info_dict['title']
            m['description'] = youtube_info_dict['description']
            youtube_info_dict['subtitles'] = youtube_info_dict['subtitles']
            m['full_html'] = youtube_info_dict['description'] +  youtube_info_dict['subtitles']
            
            m['tags'].append(url_domain)
            m['tags'].append('video')

            # some videos don't have channel
            if youtube_info_dict['uploader']:
                m['tags'].append(youtube_info_dict['uploader'])

            for auto_tag in youtube_info_dict['tags']:
                m['tags'].append(auto_tag)

            self.m = m
            return

        with requests.head(url, timeout=4) as r:
            content_type= r.headers.get('content-type', 'none')

            if 'text' not in content_type:
                m['tags'].append('binary_file')
                print('url not text')
                self.m = m
                return

        article = Article(url)

        try:
            article.download()
        except ArticleBinaryDataException:
            print(f"URL {url} is binary data")
            
        try:
            article.parse()
            article.nlp()
        except:
            print(f"Article {url} not working: article not able to be parsed")
        else:
            if article.is_parsed:
                full_html = article.html
                # soup_page = BSoup(full_html, features="lxml")

                if full_html:
                    readable = Document(full_html)
                    readable_html = readable.summary()
                    readable_title = readable.title()
                    m['full_html']  = readable_html
                    m['description'] = article.summary
                else:
                    m['full_html']  = article.summary
                    m['description'] = article.summary
            else:
                m['full_html']  = url

            if readable_title:
                m['title'] = readable_title
            else:
                m['title']  = url
            
            # Add tags and keywords here
            m['tags'].append(url_domain)

            for auto_tag in article.keywords[:5]:
                m['tags'].append(auto_tag)
                    
        print('New %s: "%s", added.' % (type,  m['title'] ))
        
        self.m = m
        self.insert_mark_thread()
        
        return

    def insert_mark_thread(self):
        data = self.m

        with app.app_context():
            m = Mark(self.user_id)
            m.url = data['url']
            m.title = data['title']
            m.description = data['description']
            m.full_html = data['full_html']
            m.type = data['type']

            for auto_tag in data['tags']:
                m.tags.append(Tag(auto_tag))
            try:
                db.session.add(m)
                db.session.commit()
            except Exception as e:
                print(e)

