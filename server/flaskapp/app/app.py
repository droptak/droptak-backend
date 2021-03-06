from utils.path import fix_path
import os, json
from google.appengine.api.logservice import logservice
from google.appengine.ext.db.metadata import Kind
from flask import Flask
import logging
import random
import string
import urllib
import httplib2
import uuid
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
from User import Account 
from Tak import Tak 
from Map import Map
from Metadata import Metadata

# this fix allows us to import modues/packages found in 'lib'
fix_path(os.path.abspath(os.path.dirname(__file__)))

from flask import Flask,make_response, render_template, request, jsonify, redirect, url_for, g, session,flash
from blueprints.example.views import bp as example_blueprint


app = Flask(__name__)
app.secret_key = 'key'
currentAccount = 1

httpcodes = {
	'200':'OK',
	'400':'Bad Request',
	'403':'Forbidden',
	'404':'File Not Found',
	'501': 'Not Implemented',
}
# attaches appropriate headers to json responses
def json_success(data):
	resp = make_response(json.dumps(data), 200)
	resp.mimetype ="application/json"
	resp.headers.extend({})
	return resp

def json_response(code, message = '', headers=None):
	if not message:
		message = httpcodes.get(str(code),'')
	data = {
		'message' : message,
		'code' : code,
	}
	resp = make_response(json.dumps(data), code)
	resp.mimetype ="application/json"
	resp.headers.extend(headers or {})
	return resp

@app.route('/dash')
def logoutIndex():
		return render_template('dashboard.html')

@app.route('/')
def index():
	if "userId" in session:
		#logging.info("loggedIn=" + str(session['loggedIn']))
		account = Account.get_by_id(session['userId'])
		if account is None: # prevent interal error
			return render_template('index.html')
		lin = account.loggedIn
		if lin == False:
			return render_template('index.html')
		if lin == True:
			return render_template('dashboard.html')

	if session:
		return render_template('dashboard.html')
	else:
		return render_template('index.html')

@app.route('/favorites/',methods=['GET','POST'])
def favorites():
	user = Account.get_by_id(int( session['userId'] ))
	if user is None:
		return json_response(code=400)
	return json_success(user.getFavorites())

@app.route('/maps/',methods=['GET','POST'])
def maps():
	userMaps = getMaps(session['userId'])
	listOfMaps = []
	for mapId in userMaps:
		logging.info(mapId)
		aMap = Map.get_by_id(mapId)
		listOfMaps.append(aMap.to_dict())
	return json_success(listOfMaps)

@app.route('/logout',methods=['GET','POST'])
def logout():
	if request.method == 'POST':
		name = session['username']
		account = Account.query(Account.name == name).get()
		account.loggedIn = False
		account.put()
		logging.info("session before " + str(len(session)))
		logging.info("session after " + str(len(session)))
		session['loggedIn'] = False
		logging.info("session set to loggedin = false")
		session.clear() 
		return '200'

	if request.method == 'GET':
		return render_template('logout.html')

@app.route('/login',methods=['GET','POST'])
def login():
		if request.method == 'POST':
			name = request.args.get("name","")
			email =  request.args.get("email","")
			logging.info("name " + name +" email " + email)
			account = Account.query(Account.email == email).get()
			#create a state string
			state = ''
			for x in xrange(32):
				state+= random.choice(string.ascii_uppercase + string.digits)
    		session['state'] = state
    		storeToken = request.args.get("storeToken","")

    	#verify store token with google servers

    		try:
    			oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
    			oauth_flow.redirect_uri = 'postmessage'
    			credentials = oauth_flow.step2_exchange(storeToken)
    		except FlowExchangeError:
    			logging.info("error with Oauth")
    			return page_not_found(404)

	    	# once store token verified send a request for credential for gplus
	    	access_token = credentials.access_token
	    	logging.info(access_token)
	    	url = ("https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s"% access_token)
	    	h = httplib2.Http()
	    	result = json.loads(h.request(url,'GET')[1])
	    	gplus_id = credentials.id_token['sub']
	    	stored_credentials = session.get('credentials')
	    	stored_gplus_id = session.get('gplus_id')

	    	if account is not None:
	    		logging.info("User already logged in")
	    		account = Account.query(Account.email == email).get()
	    		account.loggedIn = True
	    		account.put()
	    		session['credentials'] = credentials
	    		session['gplus_id'] = gplus_id
	    		session['username'] = account.name
	    		session['userId'] = account.key.integer_id()
	    		session['loggedIn'] = True


	    	else:
	    		logging.info("first time logging in")
	    		session['credentials'] = credentials
	    		session['gplus_id'] = gplus_id
	    		session['username'] = name 
	    		account = Account(name=name,email=email,gplusId=gplus_id,accessToken = access_token,loggedIn=True)
	    		key = account.put()
	    		session['userId'] = key.integer_id()
	    		session['loggedIn'] = True
	    	return '200'

		if request.method == 'GET':
			return page_not_found(404)

@app.route('/app/')
def route_view_app():
	return render_template('view_maps.html', id=int(session['userId']));


@app.route('/create/',methods=['GET','POST'])
def create_tak():
	if request.method == 'POST':
		# login required
		mapId = getValue(request, "mapId", "")
		logging.info("mapId="+mapId)
		map = Map.get_by_id(int(mapId))
		if map is None:
			return jsonify(message="Map does not exist", response=400) 
		logging.info("mapid %s" %mapId)
		name = getValue(request, "title", "")
		lat = getValue(request, "lat", "")
		lng = getValue(request, "lng", "")
		#user = getValue(request, "user", "")
		#change form to not supply user
		user = session['username']
		uid = session['userId']
			
		if not ( user and lat and lng ):
			return jsonify(message="Bad Request", response=400)
			# check if args blank

		logging.info("Add lat %s, lng %s" %(lat, lng) )
		tak  = Tak(lng=lng,lat=lat, creator=user, name=name,mapId=int(mapId),creatorId=int(uid))
		key = tak.put()
		map.takIds.append(int(key.id()))
		map.put();
		return json_success(tak.to_dict())

	if request.method == 'GET': 
		# return list of maps too for selecting
		listOfMaps = []
		mapIds = getMaps(session['userId'])
		for mapid in mapIds:
			ownMap = Map.get_by_id(mapid)
			listOfMaps.append(ownMap)

		return render_template('create_tak.html', uid=session['userId'])

@app.route('/delete/', methods=['DELETE'])
def delete_tak(mapid=-1, takid=-1):
	if request.method == 'DELETE':
		map = Map.get_by_id(mapid)
                logging.info("DELETE " + str(mapid))
                if map is not None:
                        # remove taks in map
                        tak = Tak.get_by_id(int(takid))
                        logging.info("_DELETE sub-tak" + str(takid))
                        if tak is not None:
                     		   tak.key.delete()
                        return "Success"
                return "Map does not exist"

@app.route('/maps/<str>/',methods=['GET','POST'])
@app.route('/maps/<int:mapId>/',methods=['GET','POST'])
def taks(mapId=-1, str=''):
	if mapId == -1:
		return redirect('/app')
	map = Map.get_by_id(mapId)
	if map is None:
		return redirect('/app')
	taks = map.to_dict()['taks']
	return render_template('view_taks.html',taks = taks, mapName=map.name, mapid=map.key.integer_id(), id=int(session['userId']))
	
@app.route('/taks/<int:id>', methods = ['GET', 'POST'])
def show_taks(id=-1):
	uid = -1
	try:
		uid = session['userId']
	except Exception as e:
		logging.info('no session id on /tak/<id>')
	if request.method == 'GET':
		if id >= 0:
			tak = Tak.get_by_id(id)
			if tak is not None:
				return tak.view(uid = uid)
	return redirect('/app')

@app.route('/maps/new', methods=['GET','POST'])
def create_map():
	if request.method == 'GET':
		return '200'
	if request.method == 'POST':
		user =  session['username']
		userId = session['userId']
		mapName = getValue(request, "name", "")
		isPublic = getValue(request, "isPublic","")
		return newMap(userid=userId, name=mapName,public=isPublic )

def newMap(userid='', name='', public=''):
	if not (name and public and userid):
		return json_response(code=400);
	user = Account.get_by_id(int(userid))
	if user is None:
		return json_response(code=400);
	if public == 'true':
		public = True
	else: # default false if not set
		public = False
	for mapid in user.adminMaps:
			map = Map.get_by_id(int(mapid))
			if map is not None and map.creatorId == int(userid) and map.name == name:
				return json_response(message="You already have a map of that name", code=400);
	map = Map(creator=user.name,creatorId=int(userid),name=name,adminIds=[int(userid)], public=public)
	key = map.put()
	# add map to user's list of maps
	user.adminMaps.append(key.integer_id())
	user.put()
	#return map json
	return json_success(map.to_dict());

@app.route('/map/admin/<int:mapId>/<string:email>',methods=['GET','POST'])
def admin_add(mapId,email):
	if request.method == 'POST':
		logging.info("email="+email)
		user = session['username']
		uid = session['userId']
		map = Map.get_by_id(mapId)
		adminAccount = Account.query(Account.email == email).get()
		if adminAccount == None:
			return json_response(message="No Account with that email exists",code=400)

		adminId = adminAccount.key.integer_id()
		if adminId not in map.adminIds:
			map.adminIds.append(adminId)
			map.put()
		if mapId not in adminAccount.adminMaps:
			adminAccount.adminMaps.append(mapId)
			adminAccount.put()

		return '200'

@app.route('/search', methods=['GET','POST'])
def search():
	if request.method == 'GET':
		maps = []
		mapIds = []
		queryType=request.args.get("queryType","")
		query = request.args.get("query","")
		uid = session['userId']
		account = Account.get_by_id(uid) 
		logging.info("searching for " + queryType + " " + query)
		mapQuery = Map.query(Map.public == True)
		for map in mapQuery:
			if queryType == 'searchMaps':
				if(query.lower() == map.name.lower()):
					logging.info("match!")
					maps.append(map)
					mapIds.append(map.key.integer_id())
		for mapId in account.adminMaps:
			m = Map.get_by_id(mapId)
			if (query.lower() == m.name.lower()):
				if mapId not in mapIds:
					maps.append(m)
		logging.info(len(maps))
		return render_template('search.html',maps=maps)


@app.errorhandler(404)
def page_not_found(e):
	return '404: Page Not Found' 

def getValue(request, key, default):
	value = default
	if request is not None:
		value = request.args.get(key, default)
		if value is default:
			try:
				value = request.form[key]
			except KeyError:
				value = default
	return value

def getUserMaps(id):
	logging.info("getUserMaps id is " + str(id))
	query = Map.query(Map.creatorId == id)
	return query

def getMaps(id):
	account = Account.get_by_id(id)
	return account.adminMaps

def getMapTaks(id):
	query = Tak.query(Tak.mapId == int(id))
	return query

# returns taks in map
@app.route('/api/maps/<int:id>/', methods=['GET','POST', 'DELETE', 'PUT'])
def api_taks(id=-1):
	if request.method == 'GET':
		map = Map.get_by_id(id)
		if map is None:
			return json_success({})
		else:
			return json_success(map.Get())
	if request.method == 'DELETE':
		map = Map.get_by_id(id)
		if map is None:
			return json_response(code=400, message="Map does not exist")
		map.Delete()
		return json_response(code=200,message="Success")
		
@app.route('/api/login',methods=['GET','POST'])
def api_login():
		logging.info("api_login Type "+ request.method)
		if request.method == 'POST':
			name = request.args.get("name","")
			email =  request.args.get("email","")
			logging.info("name " + name +" email " + email)


    		# once store token verified send a request for credential for gplus
	    	access_token = request.args.get("storeToken","")
	    	gplus_id = request.args.get("id","")
	    	logging.info(access_token)
	    	url = ("https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s"% access_token)
	    	h = httplib2.Http()
	    	result = json.loads(h.request(url,'GET')[1])
	    	query = Account.query(Account.email == email)
	    	account = query.get()
	    	if query.count() != 0:
	    		logging.info("Account Already Exists")
	    		key = account.key
	    		return json_success({"uuid":key.integer_id() })

	    	logging.info("first time logging in")
	    	session['gplus_id'] = gplus_id
	    	session['username'] = name 
	    	account = Account(name=name,email=email,gplusId=gplus_id,accessToken=access_token,loggedIn=True)
	    	key = account.put()
	    	session['userId'] = key.integer_id()
    		return json_success({"uuid":key.integer_id()})

		if request.method == 'GET':
			return page_not_found(404)
@app.route('/api/map',methods=['GET','POST'])
def api_map():
	if request.method == 'POST':
		userName = request.args.get("username","")
		mapName = request.args.get("mapname","")
		userId = request.args.get("userId","")
		userId = str(userId.encode('utf-8').decode('ascii', 'ignore'))
		uid = int(userId)
		ownMap =Map(creator=userName,creatorId=uid,name=mapName)
		key = ownMap.put()
		return json_success({"mapId":key.integer_id()}) 

	if request.method == 'GET':
		id = request.args.get("id","")
		ownMap = Map.get_by_id(int(id))
		return json_success({"creator":ownMap.creator,"name":ownMap.name,"creatorId":ownMap.creatorId,"id":int(id)})

@app.route('/api/tak',methods=['GET','POST'])
def api_tak():
	if request.method == 'POST':
		userName = request.args.get("name","")
		mapId = request.args.get("mapId","")
		mapId = str(mapId.encode('utf-8').decode('ascii', 'ignore'))
		userId = request.args.get("id","")
		userId = int(str(userId.encode('utf-8').decode('ascii', 'ignore')))
		name = request.args.get("title","")
		lat = request.args.get("lat","")
		lat = str(lat.encode('utf-8').decode('ascii', 'ignore'))
		lng = request.args.get("lng","")
		lng =str(lng.encode('utf-8').decode('ascii', 'ignore'))
		tak = Tak(name=name,lat=lat,lng=lng,creator=userName,creatorId=int(userId),mapId=int(mapId))
		key = tak.put()
		logging.info("tak added")
		return json_success({"takId":key.integer_id()})
	if request.method == 'GET':
		return '200'

@app.route('/api/tak/<int:id>',methods=['GET','POST','PUT', 'DELETE'])
def api_single_tak(id=-1):
	tak = Tak.get_by_id(id)
	if tak is None:
		return '404: '

	if request.method == 'GET':
		return json_success(tak.to_dict())

	if request.method == 'DELETE':
		tak.Delete()
		return json_response(code=200,message="Success")

	if request.method == 'PUT':
		name = getValue(request, "name", "")
		logging.info("name: " + name)
		tak.update(name=name)
		tak.put()
		return '200'

	if request.method == 'POST':
		return '200'

#
# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
#
# 						START OFFICIAL API ROUTING
#
# 
# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@


# ********************************************************
#					Users
# ********************************************************

#/api/v1/user/<user_id>/
@app.route('/api/v1/user/<int:userid>/',methods=['GET'])
def userData(userid = -1):
	if userid <= 0:
		return json_response(code=400)
	user = Account.get_by_id(userid)
	if user is None:
		return json_response(code=400)

	if request.method == 'GET': # done
#	GET: returns json object of user
		return json_success(user.Get())
#	these require higher security:
#	PUT: update user info
#	DELETE: delete user

@app.route('/api/v1/login',methods=['POST'])
def api_login():
		logging.info("api_login Type "+ request.method)
		if request.method == 'POST':
			name = request.args.get("name","")
			email =  request.args.get("email","")
    		# once store token verified send a request for credential for gplus
	    	access_token = request.args.get("oauth","")
	    	gplus_id = request.args.get("gplusid","")

	    	#check for valid arguments
	    	if name == "" or email == "" or access_token == "" or gplus_id == "":
	    		return json_response(code=400)

	    	url = ("https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s"% access_token)
	    	h = httplib2.Http()
	    	result = json.loads(h.request(url,'GET')[1])
	    	query = Account.query(Account.email == email)
	    	account = query.get()
	    	if query.count() != 0:
	    		key = account.key
	    		return json_success({"uuid":key.integer_id() })

	    	session['gplus_id'] = gplus_id
	    	session['username'] = name 
	    	account = Account(name=name,email=email,gplusId=gplus_id,accessToken=access_token,loggedIn=True)
	    	key = account.put()
	    	session['userId'] = key.integer_id()
    		return json_success({"uuid":key.integer_id()})
    	


# ********************************************************
#					User's Maps
# ********************************************************

@app.route('/api/v1/user/<int:userid>/maps/',methods=['GET'])
def mapsForUser(userid = -1):
	if userid <= 0:
		return json_response(code=400)
	user = Account.get_by_id(userid)
	if user is None:
		return json_response(code=400)

	if request.method == 'GET': # done
		#	GET: returns json array of information about user's map objects
		return json_success(user.getMaps())

@app.route('/api/v1/user/<int:userid>/maps/info/',methods=['GET'])
def mapInfoForUser(userid = -1):
	if userid <= 0:
		return json_response(code=400)
	user = Account.get_by_id(userid)
	if user is None:
		return json_response(code=400)

	if request.method == 'GET': # done
		#	GET: returns json array of information about user's map objects
		return json_success(user.getMapsInfo())

# ********************************************************
#					Maps
# ********************************************************

@app.route('/api/v1/map/',methods=['POST'])
def apiCreateMap():
	name = getValue(request, "name", "")
	isPublic = getValue(request, "isPublic", "")
	owner = getValue(request, "owner", "")
	return newMap(userid=owner, name=name,public=isPublic )

@app.route('/api/v1/map/<int:mapid>/',methods=['GET','PUT', 'DELETE'])
def mapData(mapid = -1):
	if mapid <= 0:
		return json_response(code=400)
	map = Map.get_by_id(mapid)
	if map is None:
		return json_response(code=400)

	if request.method == 'GET': # done
		# returns json map info
		return json_success(map.Get())

	if request.method == 'DELETE': #todo
		# DELETE: used to delete a map object and all associated tak objects, parameters: none
		map.Delete()
		return json_response(code=200,message="Success")
		

	if request.method == 'PUT': #todo
		#PUT: 	used to update map in database, parameters: (any map parameter)
		# return json map object
		newName = request.args.get("name","")
		newIsPublic = request.args.get("isPublic","")
		newOwner = request.args.get("owner","")
		map.Put(newName=newName,newIsPublic=newIsPublic,newOwner=newOwner)
		return json_response(code=200,message="Success")

@app.route('/api/v1/map/<int:mapid>/admin/<string:email>/',methods=['POST','DELETE'])
def mapAdmin(mapid=-1,email=""):
	if mapid <= 0:
		return json_response(code=400)
	if email == "":
		return json_response(code=400)

	map = Map.get_by_id(mapid)

	if map is None:
		return json_response(code=400)

	adminAccount = Account.query(Account.email == email).get()

	if adminAccount is None:
		return json_response(code=400)
	userid = adminAccount.key.integer_id()

	if request.method == 'POST':
		if userid not in map.adminIds:
			map.adminIds.append(userid)
			map.put()

		else:
			return json_success(adminAccount.Get())

		if mapid not in adminAccount.adminMaps:
			adminAccount.adminMaps.append(mapid)
			adminAccount.put()
			
		return json_success(adminAccount.Get())

	if request.method == 'DELETE':
		logging.info("delete")
		if userid not in map.adminIds:
			return json_response(code=400)

		if mapid not in adminAccount.adminMaps:
			return json_response(code=400)

		if adminAccount.key.integer_id() == map.creatorId:
			return json_response(code=400)

		map.adminIds.remove(userid)
		adminAccount.adminMaps.remove(mapid)
		map.put()
		adminAccount.put()
		return json_response(code=200)
		
# ********************************************************
#					Taks
# ********************************************************

#/api/v1/tak
@app.route('/api/v1/tak/',methods=['POST'])
def newTak():
	name = getValue(request, "name", None)
	uid = getValue(request, "userid", None)
	lat = getValue(request, "lat", None)
	lng = getValue(request, "lng", None)
	if not ( name and lat and lng and uid):
		return json_response(code=400)
	mapid = getValue(request, "mapid", None)
	map = None
	if uid is not None:
		user = Account.get_by_id(int(uid))
		if user is None:
			return json_response(code=400)
	if mapid is not None:
		map = Map.get_by_id(int(mapid))
	if map is None:
		map = Map(creator=user.name,creatorId=int(uid),name='Untitled',adminIds=[int(uid)])
		key = map.put()
		mapid = key.id()
		account = Account.get_by_id(int(uid))
		account.adminMaps.append(int(mapid))
		account.put()
	tak  = Tak(lng=lng,lat=lat, creator=user.name, name=name,mapId=int(mapid),creatorId=int(uid))
	key = tak.put()
	map.takIds.append(key.integer_id())
	map.put();
	return json_success(tak.Get())

#/api/v1/tak/<tak id>
@app.route('/api/v1/tak/<int:takid>/',methods=['GET','PUT', 'DELETE'])
def takData(takid = -1):
	if takid <= 0:
		return json_response(code=400)
	tak = Tak.get_by_id(takid)
	if tak is None:
		return json_response(code=400)

	if request.method == 'GET': # done
		# GET: returns a single json tak information
		return json_success(tak.Get())

	if request.method == 'DELETE': #todo
		# DELETE: deletes that tak
		tak.Delete()
		return json_response(code=200,message="Success")

	if request.method == 'PUT': #todo
		# PUT: updates a tak returns that object
		newName = request.args.get("name","")
		newLat = request.args.get("lat","")
		newLng = request.args.get("lng","")
		newMap = request.args.get("mapid","")
		logging.info(newMap)
		tak.Put(newName=newName,newLat=newLat,newLng=newLng, newMap = newMap)
		return json_response(code=200)

#/api/v1/tak/<tak id>
@app.route('/api/v1/tak/<int:takid>/copy/',methods=['POST'])
def copytak(takid = -1):
	if takid <= 0:
		return json_response(code=400)
	tak = Tak.get_by_id(takid)
	if tak is None:
		return json_response(code=400)
	mapid = getValue(request, "mapid", "")
	if mapid == '':
		return json_response(code=400)
	newmap = Map.get_by_id(int(mapid))
	if newmap is None:
		return json_response(code=400)
	newtak  = Tak(lng=tak.lng,lat=tak.lat, creator=tak.creator, name=tak.name,mapId=newmap.key.integer_id(),creatorId=tak.creatorId)
	newtak.metadata = tak.metadata
	key = newtak.put()
	newmap.takIds.append(key.integer_id())
	newmap.put();
	return json_success(newtak.Get())

# ********************************************************
#					Search
# ********************************************************
@app.route('/api/v1/search/', methods=["GET"])
def apiSearch():
	queryType = request.args.get("query_type","")
	query = request.args.get("query","")
	maps = []
	mapsResult = []
	resp = []
	result = {}
	result["result_type"] = "map"
	if queryType == "" or query == "":
		return json_response(code=400)


	if queryType == "mapName" or queryType == "location" or queryType == "keyword":
		if queryType == "mapName":
			mapQuery = Map.query(Map.public == True)
			for map in mapQuery:
				if(query.lower() == map.name.lower()):
					mapsResult.append(map.to_dict())
		result["result"] = mapsResult
		resp.append(result)
		return json_success(resp)

# ********************************************************
#					Favorites
# ********************************************************

@app.route('/api/v1/user/<int:userid>/favorites/',methods=['GET', 'POST', 'DELETE'])
def favorite_mapsForUser(userid = -1):
	if userid <= 0:
		return json_response(code=400)
	user = Account.get_by_id(userid)
	if user is None:
		return json_response(code=400)

	if request.method == 'GET': # done
		#	GET: returns json array of information about user's map objects
		return json_success(user.getFavorites())

	mapid = getValue(request, "mapid", "")
	if not mapid:
		return json_response(code=400)
	map = Map.get_by_id(int(mapid))
	if map is None:
		return json_response(code=400)
	if request.method == 'POST':
		if not map.key.integer_id() in user.favoriteMaps:
			user.favoriteMaps.append(map.key.integer_id())
			user.put()
		return json_response(code=200)
	
	if request.method == 'DELETE':
		if map.key.integer_id() in user.favoriteMaps:
			user.favoriteMaps.remove(map.key.integer_id())
			user.put()
		return json_response(code=200)

# ********************************************************
#					Metadata
# ********************************************************
def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv

def _decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv

@app.route('/api/v1/tak/<int:takid>/metadata/',methods=['POST', 'PUT'])
def postMetadata(takid = -1):
	if takid <= 0:
		return json_response(code=400)
	tak = Tak.get_by_id(takid)
	if tak is None:
		logging.info("tak is None")
		return json_response(code=400)
	key = getValue(request, "key", "")
	value = getValue(request, "value", "")
	if key != '' and value != '':
		for mdata in tak.metadata:
			if mdata.key == key:
				mdata.value = value
				tak.put()
				return json_response(code = 200)
		metadata = Metadata(key=key,value=value)
		tak.metadata.append(metadata)
		tak.put()
		return json_response(code = 200)
	else:
		if request.method == 'POST':
			try:
				logging.info("json")
				data = json.loads(request.data, object_hook=_decode_dict)
				logging.info(data)
				for datum in data:
					# datum is a metadata object 
					logging.info(datum['key'])
					logging.info(datum['value'])
					found = bool(0)
					for mdata in tak.metadata:
						if datum['key'] == mdata.key:
							mdata.value = datum['value']
							found = bool(1)
							break
					if not found:
						metadata = Metadata(key=datum['key'],value=datum['value'])
						tak.metadata.append(metadata)
				tak.put()

				return json_success(data)
			except Exception as e:
				logging.info(e)
				return json_response(code=400)
		return json_response(code=400)
	
@app.route('/api/v1/tak/<int:takid>/metadata/<key>/',methods=['DELETE'])
def postNewMetadata(takid = -1, key = ''):
	if not key or takid <= 0:
		return json_response(code=400)
	tak = Tak.get_by_id(takid)
	if tak is None:
		logging.info("tak is None")
		return json_response(code=400)
	try:
		logging.info(key)
		found = bool(0)
		for mdata in tak.metadata:
			if mdata.key == key:
				tak.metadata.remove(mdata)
				found = bool(1)
				break
		tak.put()
		return json_response(code=200)
	except Exception as e:
		logging.info(e)
		return json_response(code=400)
	

# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
#
# 						END OFFICIAL API ROUTING
#
#
# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

# register Blueprints
app.register_blueprint(example_blueprint)

