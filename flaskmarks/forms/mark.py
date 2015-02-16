# flaskmarks/forms/mark.py

from .base import Form, strip_filter
from ..core.setup import db
from ..models.tag import Tag
import flask.ext.whooshalchemy

from wtforms import (
    Field,
    TextField,
    TextAreaField,
    BooleanField,
    PasswordField,
    SelectField,
    RadioField,
    validators,
    HiddenField,
    IntegerField,
    SubmitField
)


class TagListField(TextField):
    """
    Code inspired from WTForms Documentation.
    http://wtforms.simplecodes.com/docs/1.0.2/fields.html#custom-fields
    """

    def _value(self):
        if self.data:
            return u' '.join([t.title for t in self.data])
        else:
            return u''

    def process_formdata(self, valuelist):
        if valuelist:
            tags = []
            tag_keys = {}
            form_tags = valuelist[0].strip().replace(',', ' ').split(' ')
            for t in form_tags:
                tag_keys[t] = 1
            for t in tag_keys.keys():
                tag = Tag.check(t.lower())
                if not tag:
                    tag = Tag(t.lower())
                    db.session.add(tag)
                tags.append(tag)
            self.data = tags
        else:
            self.data = []


class YoutubeChannelField(TextField):

    def process_formdata(self, valuelist):
        data = valuelist[0].strip()
        url = "http://gdata.youtube.com/feeds/api/users/%s/uploads"\
              % (data)
        url = url + "?max-results=30"
        self.data = url


class MarkForm(Form):
    referrer = HiddenField([validators.URL(require_tld=False)])
    title = TextField('Title',
                      [validators.Length(min=0, max=255)],
                      filters=[strip_filter])

    description = TextAreaField(u'Description',
                                [validators.optional(),
                                validators.length(max=4096)])

    url = TextField('URL',
                    [validators.Length(min=4, max=512),
                     validators.URL(require_tld=False,
                                    message='Not a valid URL')],
                    filters=[strip_filter])
    tags = TagListField('Tags',
                        [validators.Length(min=0, max=255)])
    submit_button = SubmitField('Save')


class MarkEditForm(MarkForm):
    clicks = IntegerField('Clicks')
    submit_button = SubmitField('Save')


class YoutubeMarkForm(Form):
    referrer = HiddenField([validators.URL(require_tld=False)])
    title = TextField('Title',
                      [validators.Length(min=0, max=255)],
                      filters=[strip_filter])
    url = YoutubeChannelField('User/Channel',
                              [validators.Length(min=3, max=255)],
                              filters=[strip_filter])
    tags = TagListField('Tags',
                        [validators.Length(min=0, max=255)])
    submit_button = SubmitField('Save')


class YoutubeEditForm(YoutubeMarkForm):
    clicks = IntegerField('Clicks')
    submit_button = SubmitField('Save')
