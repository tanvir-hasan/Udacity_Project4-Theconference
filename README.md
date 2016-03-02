**This is the Conference Organization App Final project created by Tanvir Hasan.**


At the beginning of the class, Udacity provided the example files for the project.

 Link: https://github.com/udacity/ud858

Now I'm describing my steps for this project:

Step One: Create new sessions for the conference

In this step I added the speakers as separate entities with the fields and types

a. name
b. bio

Here the field 'name' is added as StringProperty. It has a length limit of 1500 bytes. 

I used a TextProperty for the field 'bio'. It supports the size of the data.

Sessions are added with the following fields and types:

a. sessionName
b. highlights
c. speaker
d. duration
e. typeOfSession
f. date
g. startTime

Now the 'sessionName' and 'highlights' should be indexed. Then I used StringProperty with the length limit of 1500 bytes.

The 'speaker' refers to a Speaker entity. NDB data store offers the property type KeyProperty. It can be given the kind of the entity the field is referring to. So in this case, 'kind' means 'Speaker'.

I've added 'duration' for the duration of the specific speaker session. User can add time in minutes unit.

Here 'typeOfSession' is a StringProperty. The value is restricted to the values defined in the Enum 'sessionType':

a. WORKSHOP
b. LECTURE
c. TUTORIAL
d. BOF
e. UNSPECIFIED

Now 'date' and 'startTime'. DateProperty and TimeProperty have been used for them. Getting the start time on its own in a separate property makes some queries very handy.

The following forms have been used in the project:

a. speakerForm
b. speakerMiniForm
c. speakerForms
d. sessionType
e. sessionForm
f. sessionMiniForm
g. sessionForms

The following URL paths and HTTP methods have been used in this step:

a. /speaker, POST, createSpeaker()
b. /speakers, GET, getSpeakers()
c. /session/{websafeConferenceKey}, POST, createSession()
d. /sessions/{websafeConferenceKey}, GET, getConferenceSessions()
e. /sessions_by_type/{websafeConferenceKey}, POST, getConferenceSessionsByType()
f. /sessions_by_speaker, POST, getSessionsBySpeaker()


Step Two: Create new sessions for the User wishlist:

Session can be added by the app users to their wishlist.

Following options have been used to manage the wishlist:

WISHLIST_REQUEST
CONF_WISHLIST_GET_REQUEST

The following URL paths and HTTP methods have been used in this step:

a. /wishlist/{websafeSessionKey}, POST, addSessionToWishlist()
b. /wishlist/{websafeSessionKey}, DELETE, removeSessionFromWishlist()
c. /wishlist, GET, getWishlistSessions()
d. /wishlist, GET, getSessionsInWishlist()


Step Three: Work on indexes and queries:

1. Indexes:

I've added the following index to support the query for the functionality:

a. kind: Session
b. properties:
  - name: __key__
  - name: startTime
  
No need to add indexes to support queries from tasks 1 and 2.

2. Queries:

To list all conferences for the given topic, I have created the following forms:

a. TopicForm
b. TopicForms

The following URL paths and HTTP methods have been used to get topic search API methods:

a. /topics, 'GET', getTopics() : Returns topics information.
b. /conferencesbytopic, 'POST', getConferencesByTopic() : Returns a conference's topic occurring same day or later.

There are some limitations when using ndb/Datastore queries. Because queries are allowed to have on inequality filter only. For solution, we can query sessions before 7 pm with ndb and then manually filter that list with Python to remove sessions with a workshop type.


Step Four: Add a new task

I've changed the following files to add a new task:

app.yaml: Defined the task in app.yaml by using the path /tasks/check_featured_speaker

conference.py: This task is put into the push queue from the private method _createSessionObject(), which is called by the API method createSession()

main.py: The path of this task is registered  with the app object in main.py .

conference.py: The private method _cacheFeaturedSpeaker() is called by this request.


Now I'm describing the steps to run this project:

You'll need the following environment set up

a. Products (App Engine)
b. Language (Python)
c. APIs (Google Cloud Endpoints)

If you are ready, you can follow the instructions to run the project:

a. Open the app.yaml file and update with your own project ID
b. Now open the settings.py file and update with your Web Client ID
c. Then open the app.js file and update with your Web Client ID
d. Open your Google App Engine software & add the project
e. Now run & visit localhost:your_port(8080 by default)
f. Deploy your application to visit the live app and share the live url with others!! the url should be https://your_app_id.appspot.com

If you face any issues or want suggest me to improve the project, email to tanvir@mrsft.com

Thanks!!
