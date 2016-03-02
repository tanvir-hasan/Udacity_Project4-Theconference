#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints




"""

__author__ = 'wesc+api@google.com (Wesley Chun), tanvir@mrsft.com (Tanvir Hasan)'


from datetime import datetime

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import TeeShirtSize
from models import StringMessage
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import Session
from models import SessionForm
from models import SessionMiniForm
from models import SessionForms
from models import SessionQueryByTypeForm
from models import SessionQueryBySpeakerForm
from models import SessionQueryBeforeExcludingForm
from models import SessionType
from models import Speaker
from models import SpeakerForm
from models import SpeakerForms
from models import SpeakerMiniForm
from models import TopicForm
from models import TopicForms


from settings import WEB_CLIENT_ID
from settings import ANDROID_CLIENT_ID
from settings import IOS_CLIENT_ID
from settings import ANDROID_AUDIENCE

from utils import getUserId

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
MEMCACHE_FEATURED_SPEAKER_KEY = "RECENT FEATURED SPEAKER"
ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')
FEATURED_SPEAKER_TPL = ('Featured speaker in %s: %s with the sessions: %s')
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

CONF_DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": [ "Default", "Topic" ],
}

SESSION_DEFAULTS = {
    "typeOfSession": "UNSPECIFIED"
}

OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }

CONF_FIELDS =    {
            'CITY': 'city',
            'TOPIC': 'topics',
            'MONTH': 'month',
            'MAX_ATTENDEES': 'maxAttendees',
            }

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1)
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1)
)

SESSION_POST_REQUEST = endpoints.ResourceContainer(
    SessionMiniForm,
    websafeConferenceKey=messages.StringField(1))

SESSION_QUERY_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1)
)

SESSION_QUERY_BY_TYPE_REQUEST = endpoints.ResourceContainer(
    SessionQueryByTypeForm,
    websafeConferenceKey=messages.StringField(1)
)

WISHLIST_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSessionKey=messages.StringField(1)
)

CONF_WISHLIST_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1)
)

SESSIONS_BEFORE_EXCLUDING_POST_REQUEST = endpoints.ResourceContainer (
    SessionQueryBeforeExcludingForm,
    websafeConferenceKey=messages.StringField(1)
)

FEATURED_SPEAKER_GET_REQUEST = endpoints.ResourceContainer (
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    websafeSpeakerKey=messages.StringField(2)
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

@endpoints.api( name='conference', version='v1', audiences=[ANDROID_AUDIENCE],
    allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID, ANDROID_CLIENT_ID, IOS_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

# - - - Profile objects - - - - - - - - - - - - - - - - - - -

    ## profile helpers
    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name, getattr(TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf

    def _getProfileFromUser(self):
        """Return user Profile from datastore, creating new one if non-existent."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = getUserId(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()

        # create new Profile if not there
        if not profile:
            profile = Profile(
                key = p_key,
                displayName = user.nickname(),
                mainEmail= user.email(),
                teeShirtSize = str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile

    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
            prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)
    ## end profile helpers

    ## profile api methods
    # /profile, GET, getProfile()
    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()

    # /profile, POST, saveProfile()
    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return self._doProfile(request)

    ## end profile api methods

# - - - Conference objects - - - - - - - - - - - - - - - - -

    ## conference helpers
    def _copyConferenceToForm(self, conf, displayName):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf

    def _createConferenceObject(self, request):
        """Create Conference object, returning ConferenceForm/request."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing (both data model & outbound Message)
        for df in CONF_DEFAULTS:
            if data[df] in (None, []):
                data[df] = CONF_DEFAULTS[df]
                setattr(request, df, CONF_DEFAULTS[df])

        # convert dates from strings to Date objects; set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        # both for data model & outbound Message
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
            setattr(request, "seatsAvailable", data["maxAttendees"])

        # make Profile Key from user ID
        p_key = ndb.Key(Profile, user_id)
        # allocate new Conference ID with Profile key as parent
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        # make Conference key from ID
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference & return (modified) ConferenceForm
        Conference(**data).put()
        taskqueue.add(params={'email': user.email(),
            'conferenceInfo': repr(request)},
            url='/tasks/send_confirmation_email'
        )

        return request

    @ndb.transactional()
    def _updateConferenceObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))

    def _getConferenceQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q
    ## end conference helpers

    ## conference api methods
    # /conference, POST, createConference()
    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)

    # /conference/{websafeConferenceKey}, PUT, updateConference
    @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """Update conference w/provided fields & return w/updated info."""
        return self._updateConferenceObject(request)

    # /conference/{websafeConferenceKey}, GET, getConference()
    @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='GET', name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)
        prof = conf.key.parent().get()
        if not prof:
            raise endpoints.NotFoundException(
                'Conference does not have an ancestor.')
        # return ConferenceForm
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))

    # /conferences, POST, queryConferences()
    @endpoints.method(ConferenceQueryForms, ConferenceForms,
            path='conferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getConferenceQuery(request)

         # return individual ConferenceForm object per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, "") \
            for conf in conferences]
        )

    # /conferences/created, GET, getConferencesCreated()
    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/created',
            http_method='GET', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, getattr(prof, 'displayName')) for conf in confs]
        )

    # /conferences/attending, GET, getConferencesToAttend()
    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/attending',
            http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._getProfileFromUser() # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck) for wsck in prof.conferenceKeysToAttend]
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[self._copyConferenceToForm(conf, names[conf.organizerUserId])\
         for conf in conferences]
        )

    ## end conference api methods

# - - - Sessions - - - - - - - - - - - - - - - - - - - - - -

    ## session helpers
    def _copySessionToForm(self, session):
        """Copy relevant fields from Session to SessionForm."""
        sf = SessionForm()
        for field in sf.all_fields():
            if hasattr(session, field.name):
                # convert Date to date string and Time to time string
                if field.name.endswith('date') or field.name.endswith('Time'):
                    setattr(sf, field.name, str(getattr(session, field.name)))
                # convert session typeOfSession string to Enum; 
                elif field.name == 'typeOfSession':
                    #setattr(sf, field.name, getattr(session, field.name))
                    setattr(sf, field.name, getattr(SessionType, getattr(session, field.name)))               
                # just copy others                   
                else:
                    setattr(sf, field.name, getattr(session, field.name))

        # show the session's own websafe key
        setattr(sf, 'websafeKey', session.key.urlsafe())

        # show the conference name
        if session.key and session.key.parent():
            conf = session.key.parent().get()
            setattr(sf, 'conferenceName', getattr(conf, 'name'))
        else:
            setattr(sf, 'conferenceName', 'not set')

        # if the session has a speaker assigned, show their name and websafe key
        if hasattr(session, 'speaker'):
            sp_key = getattr(session, 'speaker')
            if sp_key:
                speaker = sp_key.get()
                setattr(sf, 'speakerName', getattr(speaker, 'name'))
                setattr(sf, 'websafeSpeakerKey', speaker.key.urlsafe())

        sf.check_initialized()
        return sf

    def _createSessionObject(self, request):
        """Create Session object, returning SessionForm/request."""

        # check for auth'ed and valid user
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # no default values used, but at least one field must be filled
        if not request.sessionName:
            raise endpoints.BadRequestException("Field 'sessionName' required")

        # sessions belong to conferences, so: websafe conference key given?
        if not request.websafeConferenceKey:
            raise endpoints.BadRequestException("Field 'websafeConferenceKey' required")

        # websafe conference key good?
        try:
            c_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        except Exception:
            raise endpoints.BadRequestException("websafeConferenceKey given is corrupted")
        if not c_key:
            raise endpoints.BadRequestException("websafeConferenceKey given is invalid") 

        # does the conference (still) exist?
        conf = c_key.get()
        if not conf:
            raise endpoints.NotFoundException("Conference with this key does not exist")

        # only the conference organizer may add sessions, check
        if user_id != conf.organizerUserId:
            raise endpoints.UnauthorizedException('Only the conference organizer may add session')

        # copy SessionForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        # convert date from string to Date object
        if data['date']:
            data['date'] = datetime.strptime(data['date'][:10], "%Y-%m-%d").date()

        # convert startTime from string to Date object
        if data['startTime']: 
            data['startTime'] = datetime.strptime(data['startTime'][:5], "%H:%M").time()

        # convert sessionType to string
        if data['typeOfSession']:
            data['typeOfSession'] = str(data['typeOfSession'])

        # add default values for those missing (both data model & outbound Message)
        for df in SESSION_DEFAULTS:
            if data[df] in (None, []):
                data[df] = SESSION_DEFAULTS[df]


        # sessions may have speakers, if it is given, check for validity:
        if request.websafeSpeakerKey:
            # speaker key good?
            try:
                sp_key = ndb.Key(urlsafe=request.websafeSpeakerKey)
            except Exception:
                raise endpoints.BadRequestException("websafeSpeakerKey given is corrupted")
            if not sp_key:
                raise endpoints.BadRequestException("websafeSpeakerKey given is invalid")
            else:
                data['speaker'] = sp_key
        elif request.speakerName:
            # is there exactly one speaker of this name?
            speakers = Speaker.query()
            speakers = speakers.filter(Speaker.name == request.speakerName)
            if speakers.count() == 0:
                raise endpoints.NotFoundException(
                    "No such speaker: %s" % request.speakerName)
            elif speakers.count() > 1:
                raise endpoints.BadRequestException(
                    "Speaker name ambiguous: %s" % request.speakerName)
            else:
                data['speaker'] = speakers.get().key

        # remove unnecessary data copied over from request
        del data['websafeConferenceKey']
        if hasattr(data, 'conferenceName'):
            del data['conferenceName']
        del data['websafeSpeakerKey']
        del data['speakerName']

        # allocate new Session ID with Conference key as parent
        s_id = Session.allocate_ids(size=1, parent=c_key)[0]
        # make Session key from ID
        s_key = ndb.Key(Session, s_id, parent=c_key)
        data['key'] = s_key

        # create Session & return (modified) SessionForm
        session = Session(**data)
        session.put()

        # add a task to check if the speaker of this new session is
        # now a featured speaker
        if hasattr(session, 'speaker') and getattr(session, 'speaker'):
            print "adding task now to queue"
            taskqueue.add(params={'websafeConferenceKey': request.websafeConferenceKey,
                'websafeSpeakerKey': getattr(session, 'speaker').urlsafe()},
                url='/tasks/check_featured_speaker'
            )
        else:
            print "session has no speaker any more"

        return self._copySessionToForm(session)

    def _getSessionQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Session.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Session.sessionName)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Session.sessionName)

        for filtr in filters:
            if filtr["field"] in ["duration"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q

    ## end session helpers

    ## session api methods
    # /session/{websafeConferenceKey}, POST, createSession()
    @endpoints.method(SESSION_POST_REQUEST, SessionForm, 
            path='session/{websafeConferenceKey}',
            http_method='POST', name='createSession')
    def createSession(self, request):
        """Create new session."""
        return self._createSessionObject(request)

    # /sessions/{websafeConferenceKey}, GET, getConferenceSessions()
    @endpoints.method(SESSION_QUERY_REQUEST, SessionForms,
            path='sessions/{websafeConferenceKey}',
            http_method='GET', name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """Return all sessions in a given conference."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # sessions belong to conferences, so: websafe conference key given?
        if not request.websafeConferenceKey:
            raise endpoints.BadRequestException("Field 'websafeConferenceKey' required")

        # websafe conference key good?
        try:
            c_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        except Exception:
            raise endpoints.BadRequestException("websafeConferenceKey given is corrupted")
        if not c_key:
            raise endpoints.BadRequestException("websafeConferenceKey given is invalid") 

        # does the conference (still) exist?
        conf = c_key.get()
        if not conf:
            raise endpoints.NotFoundException("Conference with this key does not exist")

        # create ancestor query for all key matches for this user
        sessions = Session.query(ancestor=c_key)
        # return set of SessionForm objects per Conference
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )


    # /sessions_by_type/{websafeConferenceKey}, POST, getConferenceSessionsByType()
    @endpoints.method(SESSION_QUERY_BY_TYPE_REQUEST, SessionForms,
            path='sessions/{websafeConferenceKey}',
            http_method='POST', name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """Return all sessions of the specified type in a given conference"""
        sessions = Session.query(ancestor=ndb.Key(urlsafe=request.websafeConferenceKey))
        #typeOfSession = getattr(SessionType, getattr(request, 'typeOfSession'))
        sessions = sessions.filter(Session.typeOfSession == str(getattr(request, 'typeOfSession')))
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )

    # /sessions_by_speaker, POST, getSessionsBySpeaker()
    @endpoints.method(SessionQueryBySpeakerForm, SessionForms,
            path='sessions_by_speaker',
            http_method='POST', name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """Return all sessions by the specified speaker in all conferences"""
        sessions = Session.query()
        sessions = sessions.filter(Session.speaker == ndb.Key(urlsafe=getattr(request, 'speaker')))
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )
    ## end session api methods

# - - - Speakers - - - - - - - - - - - - - - - - - - - - - -

    ## speaker helper methods
    def _copySpeakerToForm(self, speaker):
        """Copy relevant fields from Speaker to SpeakerForm."""
        sf = SpeakerForm()
        for field in sf.all_fields():
            if hasattr(speaker, field.name):
                setattr(sf, field.name, getattr(speaker, field.name))
            elif field.name == "websafeKey":
                setattr(sf, field.name, speaker.key.urlsafe())
        sf.check_initialized()
        return sf

    def _createSpeakerObject(self, request):
        """Create Speaker object, returning SpeakerForm."""

        # check for auth'ed and valid user
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # Speaker name must be filled
        if not request.name:
            raise endpoints.BadRequestException("Field 'name' required")

        # copy SpeakerForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        # allocate new Speaker ID
        s_id = Speaker.allocate_ids(size=1)[0]
        # make Speaker key from ID
        s_key = ndb.Key(Speaker, s_id)
        data['key'] = s_key

        # create Speaker & return SpeakerForm
        speaker = Speaker(**data)
        speaker.put()

        return self._copySpeakerToForm(speaker)

    ## end speaker helper methods

    ## speaker api methods
    # /speaker, POST, createSpeaker()
    @endpoints.method(SpeakerMiniForm, SpeakerForm, 
            path='speaker',
            http_method='POST', name='createSpeaker')
    def createSpeaker(self, request):
        """Create new speaker"""
        return self._createSpeakerObject(request)

    # /speakers, GET, getSpeakers()
    @endpoints.method(message_types.VoidMessage, SpeakerForms,
            path='speakers',
            http_method='GET', name='getSpeakers')
    def getSpeakers(self, request):
        """Return all speakers"""
        speakers = Speaker.query()
        return SpeakerForms(
            items=[self._copySpeakerToForm(speaker) for speaker in speakers]
        )
    ## end speaker api methods

# - - - Registration - - - - - - - - - - - - - - - - - - - -

    ## registration helpers
    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        retval = None
        prof = self._getProfileFromUser() # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        wsck = request.websafeConferenceKey
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)
    ## end registration helpers

    ## registration api methods
    # /conference/{websafeConferenceKey}, POST, registerForConference()
    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)

    # /conference/{websafeConferenceKey}, DELETE, unregisterFromConference()
    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)
    ## end registration api methods

# - - - Wishlist - - - - - - - - - - - - - - - - - - - - - -

    ## wishlist helpers
    def _wishlistToggle(self, request, add=True):
        """Add or remove user session from user's wishlist."""
        retval = False
        prof = self._getProfileFromUser() # get user Profile

        # check if session exists given websafeSessionKey
        try:
            wssk = request.websafeSessionKey
            session = ndb.Key(urlsafe=wssk).get()
        except Exception:
            raise endpoints.BadRequestException(
                'websafeSessionKey given is corrupted.')
        
        if not session:
            raise endpoints.NotFoundException(
                'No Session found with key: %s' % wsck)

        # add to wishlist
        if add:
            # check if session already added otherwise add
            if wssk in prof.sessionWishlist:
                raise ConflictException(
                    "You have already added this session to your wishlist")

            # register user, take away one seat
            prof.sessionWishlist.append(wssk)
            retval = True

        # remove from wishlist
        else:
            # is session in wishlist, remove
            if wssk in prof.sessionWishlist:
                prof.sessionWishlist.remove(wssk)
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        return BooleanMessage(data=retval)
    ## end wishlist helpers

    ## wishlist api methods
    # /wishlist/{websafeSessionKey}, POST, addSessionToWishlist()
    @endpoints.method(WISHLIST_REQUEST, BooleanMessage,
            path='wishlist/{websafeSessionKey}',
            http_method='POST', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """Add session to user's wishlist."""
        return self._wishlistToggle(request)

    # /wishlist/{websafeSessionKey}, DELETE, removeSessionFromWishlist()
    @endpoints.method(WISHLIST_REQUEST, BooleanMessage,
            path='wishlist/{websafeSessionKey}',
            http_method='DELETE', name='removeSessionFromWishlist')
    def removeSessionFromWishlist(self, request):
        """Remove session from user's wishlist."""
        return self._wishlistToggle(request, add=False)

    # /wishlist, GET, getWishlistSessions()
    @endpoints.method(message_types.VoidMessage, SessionForms,
            path='wishlist',
            http_method='GET', name='getWishlistSessions')
    def getWishlistSessions(self, request):
        """Return all sessions on user's wishlist"""
        prof = self._getProfileFromUser() # get user Profile
        session_keys = [ndb.Key(urlsafe=wssk) for wssk in prof.sessionWishlist]
        sessions = ndb.get_multi(session_keys)

        # return set of SessionForm objects
        return SessionForms(items=[self._copySessionToForm(session) \
            for session in sessions]
        )

    # /wishlist, GET, getSessionsInWishlist()
    @endpoints.method(CONF_WISHLIST_GET_REQUEST, SessionForms,
        path='wishlist/{websafeConferenceKey}',
        http_method='GET', name='getSessionsInWishlist')
    def getSessionsInWishlist(self, request):
        """Return all sessions on user's wishlist in a given conference"""
        prof = self._getProfileFromUser() # get user Profile
        # get real keys from urlsafe keys
        wl_session_keys = [ndb.Key(urlsafe=wssk) for wssk in prof.sessionWishlist]

        try:
            sessions = Session.query(ancestor=ndb.Key(urlsafe=request.websafeConferenceKey))
        except Exception:
            raise endpoints.BadRequestException(
                'websafeConferenceKey given is corrupt')

        sessions = sessions.filter(Session.key.IN(wl_session_keys))

        # return set of SessionForm objects
        return SessionForms(items=[self._copySessionToForm(session) \
            for session in sessions]
        )

    ## end wishlist api methods

# - - - Search & filtering - - - - - - - - - - - - - - - - -

    ## search & filtering helpers


    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}

            try:
                filtr["field"] = CONF_FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException("Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous filters
                # disallow the filter if inequality was performed on a different field before
                # track the field on which the inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException("Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)
    ## end search & filtering helpers

# - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = ANNOUNCEMENT_TPL % (
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement


    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='conference/announcement/get',
            http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        return StringMessage(data=memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) or "")

# - - - Query showcase (task 3)- - - - - - - - - - - - - - -

    ## task 3.2.1: list all topics covered by the conferences in the system
    # /topics, 'GET', getTopics()
    @endpoints.method(message_types.VoidMessage, TopicForms,
        path='topics', http_method='GET', name='getTopics')
    def getTopics(self, request):
        """Return a list of all topics"""
        topics = set()
        confs = Conference.query()
        for conf in confs:
            if hasattr(conf, 'topics'):
                for conftopic in getattr(conf, 'topics'):
                    topics.add(conftopic) # the set takes care of not adding duplicates

        return TopicForms(items=[TopicForm(topic=topic) for topic in topics])

    ## task 3.2.2: list all conferences covering a given topic
    # /conferencesbytopic, 'POST', getConferencesByTopic()
    @endpoints.method(TopicForm, ConferenceForms,
        path='/conferencesbytopic',
        http_method='POST', name='getConferencesByTopic')
    def getConferencesByTopic(self, request):
        """Return all conferences on a given topic"""
        confs = Conference.query()
        confs = confs.filter(Conference.topics == request.topic)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in confs]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[self._copyConferenceToForm(
            conf, names[conf.organizerUserId])\
         for conf in confs]
        )


    ## task 3.3: list all sessions NOT matching the given type scheduled after
    ## the given time
    # /sessionquery/{websafeConferenceKey}, POST, getSessionsBeforeExcluding()
    @endpoints.method(SESSIONS_BEFORE_EXCLUDING_POST_REQUEST, SessionForms,
        path='sessionquery/{websafeConferenceKey}',
        http_method='POST', name='getSessionsBeforeExcluding')
    def getSessionsBeforeExcluding(self, request):
        """Return all session after the given time and not matching the
        given session type."""

        # make time from string
        latestTime = datetime.strptime(request.latestTime[:5], "%H:%M").time()

        # query 1: all sessions in conference after latestTime
        sessions = Session.query()
        rightTimeSessions = sessions.filter(Session.startTime <= latestTime)

        # query 2: all sessions in conference not of type typeOfSession
        rightTypeSessions = sessions.filter(
            Session.typeOfSession != str(request.typeOfSession))
        filter_keys = [rts.key for rts in rightTypeSessions]

        # filter query 1 by query 2
        sessions = rightTimeSessions.filter(Session.key.IN(filter_keys))

        # return set of SessionForm objects
        return SessionForms(items=[self._copySessionToForm(session) \
            for session in sessions]
        )

# - - - Featured speaker (task 4)  - - - - - - - - - - - - -

    @staticmethod
    def _cacheFeaturedSpeaker(websafeConferenceKey, websafeSpeakerKey):
        """Find featured speaker & assign to memcache; used by
        getFeaturedSpeaker().
        """
        c_key = ndb.Key(urlsafe=websafeConferenceKey)
        sp_key = ndb.Key(urlsafe=websafeSpeakerKey)
        sessions = Session.query(ancestor=c_key)
        sessions = sessions.filter(Session.speaker==sp_key)

        if sessions.count() > 1:
            # if there is more than one session for this
            # speaker, format a featured speaker announcement
            # and put it to memcache
            # this will overwrite the last featured speaker
            sessionNames = ", ".join([session.sessionName for session in sessions])
            speaker = sp_key.get()
            conf    = c_key.get()

            announcement = FEATURED_SPEAKER_TPL % (
                conf.name, speaker.name, sessionNames)

            memcache.set(MEMCACHE_FEATURED_SPEAKER_KEY, announcement)
        else:
            announcement = ""

        return announcement

    # /featuredspeaker, GET, getFeaturedSpeaker()
    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='featuredspeaker',
            http_method='GET', name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Return Featured Speaker from memcache."""
        return StringMessage(data=memcache.get(MEMCACHE_FEATURED_SPEAKER_KEY) or "")


# - - - API registration - - - - - - - - - - - - - - - - - -

# registers API
api = endpoints.api_server([ConferenceApi]) 
