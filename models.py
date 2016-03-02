#!/usr/bin/env python

"""models.py

Udacity conference server-side Python App Engine data & ProtoRPC models

$Id: models.py,v 1.1 2014/05/24 22:01:10 wesc Exp $

created/forked from conferences.py by wesc on 2014 may 24

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

import httplib
import endpoints
from protorpc import messages
from google.appengine.ext import ndb

# - - - Profiles - - - - - - - - - - - - - - - - - - -

class Profile(ndb.Model):
    """Profile -- User profile object"""
    displayName = ndb.StringProperty()
    mainEmail = ndb.StringProperty()
    teeShirtSize = ndb.StringProperty(default='NOT_SPECIFIED')
    conferenceKeysToAttend = ndb.StringProperty(repeated=True)
    sessionWishlist = ndb.StringProperty(repeated=True)


class ProfileMiniForm(messages.Message):
    """ProfileMiniForm -- update Profile form message"""
    displayName = messages.StringField(1)
    teeShirtSize = messages.EnumField('TeeShirtSize', 2)


class ProfileForm(messages.Message):
    """ProfileForm -- Profile outbound form message"""
    userId = messages.StringField(1)
    displayName = messages.StringField(2)
    mainEmail = messages.StringField(3)
    teeShirtSize = messages.EnumField('TeeShirtSize', 4)
    conferenceKeysToAttend = messages.StringField(5, repeated=True)
    sessionWishlist = messages.StringField(6, repeated=True)


class TeeShirtSize(messages.Enum):
    """TeeShirtSize -- t-shirt size enumeration value"""
    NOT_SPECIFIED = 1
    XS_M = 2
    XS_W = 3
    S_M = 4
    S_W = 5
    M_M = 6
    M_W = 7
    L_M = 8
    L_W = 9
    XL_M = 10
    XL_W = 11
    XXL_M = 12
    XXL_W = 13
    XXXL_M = 14
    XXXL_W = 15

# - - - Conferences  - - - - - - - - - - - - - - - - -

class Conference(ndb.Model):
    """Conference -- Conference object"""
    name            = ndb.StringProperty(required=True)
    description     = ndb.StringProperty()
    organizerUserId = ndb.StringProperty()
    topics          = ndb.StringProperty(repeated=True)
    city            = ndb.StringProperty()
    startDate       = ndb.DateProperty()
    month           = ndb.IntegerProperty()
    endDate         = ndb.DateProperty()
    maxAttendees    = ndb.IntegerProperty()
    seatsAvailable  = ndb.IntegerProperty()

class ConferenceForm(messages.Message):
    """ConferenceForm -- Conference outbound form message"""
    name            = messages.StringField(1)
    description     = messages.StringField(2)
    organizerUserId = messages.StringField(3)
    topics          = messages.StringField(4, repeated=True)
    city            = messages.StringField(5)
    startDate       = messages.StringField(6)
    month           = messages.IntegerField(7)
    maxAttendees    = messages.IntegerField(8)
    seatsAvailable  = messages.IntegerField(9)
    endDate         = messages.StringField(10)
    websafeKey      = messages.StringField(11)
    organizerDisplayName = messages.StringField(12)

class ConferenceForms(messages.Message):
    """ConferenceForms -- multiple Conference outbound form message"""
    items = messages.MessageField(ConferenceForm, 1, repeated=True)

class ConferenceQueryForm(messages.Message):
    """ConferenceQueryForm -- Conference query inbound form message"""
    field = messages.StringField(1)
    operator = messages.StringField(2)
    value = messages.StringField(3)

class ConferenceQueryForms(messages.Message):
    """ConferenceQueryForms -- multiple ConferenceQueryForm inbound form message"""
    filters = messages.MessageField(ConferenceQueryForm, 1, repeated=True)

# - - - Speakers - - - - - - - - - - - - - - - - - - -

class Speaker(ndb.Model):
    """Speaker -- Session speaker object"""
    name = ndb.StringProperty()
    bio  = ndb.TextProperty()

class SpeakerForm(messages.Message):
    """SpeakerForm -- Speaker outbound form message"""
    name = messages.StringField(1)
    bio  = messages.StringField(2)
    websafeKey = messages.StringField(3)

class SpeakerMiniForm(messages.Message):
    """SpeakerMiniForm -- update Speaker inbound form message"""
    name = messages.StringField(1)
    bio  = messages.StringField(2)

class SpeakerForms(messages.Message):
    items = messages.MessageField(SpeakerForm, 1, repeated=True)

# - - - Sessions - - - - - - - - - - - - - - - - - - -

class SessionType(messages.Enum):
    """SessionType -- session types enumeration values"""
    WORKSHOP = 1
    LECTURE = 2
    BOF = 3
    TUTORIAL = 4
    UNSPECIFIED = 5

class Session(ndb.Model):
    """Session -- Conference session object"""
    sessionName   = ndb.StringProperty()
    highlights    = ndb.StringProperty()
    speaker       = ndb.KeyProperty(kind=Speaker)
    duration      = ndb.IntegerProperty()
    typeOfSession = ndb.StringProperty()
    date          = ndb.DateProperty()
    startTime     = ndb.TimeProperty()

class SessionForm(messages.Message):
    """SessionForm -- Session outbound form message"""
    sessionName    = messages.StringField(1)
    highlights     = messages.StringField(2)
    speakerName    = messages.StringField(3)
    duration       = messages.IntegerField(4)
    typeOfSession  = messages.EnumField('SessionType', 5)
    date           = messages.StringField(6)
    startTime      = messages.StringField(7)
    conferenceName = messages.StringField(8)
    websafeSpeakerKey = messages.StringField(9)
    websafeKey     = messages.StringField(10)

class SessionMiniForm(messages.Message):
    """SessionForm -- Session inbound form message"""
    sessionName    = messages.StringField(1)
    highlights     = messages.StringField(2)
    speakerName    = messages.StringField(3)
    duration       = messages.IntegerField(4)
    typeOfSession  = messages.EnumField('SessionType', 5)
    date           = messages.StringField(6)
    startTime      = messages.StringField(7)
    websafeSpeakerKey = messages.StringField(8)

class SessionQueryBySpeakerForm(messages.Message):
    """SessionQueryBySpeakerForm -- Session query inbound form"""
    speaker = messages.StringField(1)

class SessionQueryByTypeForm(messages.Message):
    """SessionQueryByTypeForm -- Session query inbound form"""
    typeOfSession = messages.EnumField('SessionType', 1)

class SessionQueryBeforeExcludingForm(messages.Message):
    """SessionQueryAfterExcludingForm -- Session query inbound form"""
    latestTime = messages.StringField(1)
    typeOfSession = messages.EnumField('SessionType', 2)

class SessionForms(messages.Message):
    """SessionForms -- multiple Session outbound form message"""
    items = messages.MessageField(SessionForm, 1, repeated=True)

# needed for topic-related search
class TopicForm(messages.Message):
    """TopicForm -- Topic query inbound / outbound form"""
    topic = messages.StringField(1)

class TopicForms(messages.Message):
    """TopicForms -- multiple Topic outbound form message"""
    items = messages.MessageField(TopicForm, 1, repeated=True)

# needed for conference registration
class BooleanMessage(messages.Message):
    """BooleanMessage-- outbound Boolean value message"""
    data = messages.BooleanField(1)

class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    data = messages.StringField(1, required=True)

class ConflictException(endpoints.ServiceException):
    """ConflictException -- exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT