from flask import Flask, jsonify, make_response, request
from werkzeug.security import generate_password_hash,check_password_hash
import os
import dotenv
from bson.json_util import dumps
from bson.objectid import ObjectId
import jwt
from datetime import datetime,timedelta
from flask_cors import CORS
from functools import wraps
dotenv.load_dotenv()
app = Flask(__name__)
CORS(app,supports_credentials=True)

# DB
from flask_pymongo import PyMongo
app.config['MONGO_URI'] = os.getenv('MONGO_URI')
JWT_SECRET = os.getenv('JWT_SECRET')
mongo = PyMongo(app)
@app.route('/')
def home():
    return 'Hello'
# Auth
@app.post('/signup')
def signUp():    
    data = request.get_json()
    uname = data.get("uname")
    password = data.get("password")
    if not uname or not password:
        return jsonify({"error":'Missing username or password'}),400
    if mongo.db.users.find_one({'uname':uname}): # type: ignore
        return jsonify({"error":'Username already been used'}),409
    else:
        hashed_password = generate_password_hash(password)
        mongo.db.users.insert_one({'uname':uname, # type: ignore
                                   'hashed_password':hashed_password})         
        return jsonify({"msg":'Sign Up Success'}),201
@app.post('/login')
def Login():
    data = request.get_json()
    uname = data.get('uname')
    password = data.get('password')
    if not uname or not password:
        return jsonify({'error':'Missing username or password'}),400
    account = mongo.db.users.find_one({'uname':uname})       # type: ignore
    if account is None:
        return jsonify({'error':'Username not found'}),400
    if not check_password_hash(account['hashed_password'],password):
        return jsonify({'error':'Wrong Password'}),400
    token = jwt.encode({'uname':uname,' hashed_password':generate_password_hash(password),'exp':datetime.now()+timedelta(hours=1)},JWT_SECRET,'HS256')
    response = make_response({'msg':'Login Success'},200) 
    response.set_cookie('token',token,max_age=3600,httponly=True,samesite='None',secure=True)
    return response            
@app.delete('/logout')
def logout():
    try:
        response = make_response({'msg':'Logout Success'},200)
        response.delete_cookie('token')
        return response
    except:
        return jsonify({'error':'Log out Failed'},400)

# Auth Helper
@app.get('/isloggedin')
def check_login():
    token = None
    token = request.cookies.get('token')
    if not token: return jsonify({'isLoggedIn':False,'err':'Token not found'})
    try:
        data = jwt.decode(token,JWT_SECRET,algorithms=['HS256'])
        current_user = mongo.db.users.find_one({'uname':data['uname']}) 
        if not current_user:
            return jsonify({'isLoggedIn':False})
        return jsonify({'isLoggedIn':True})
    except jwt.ExpiredSignatureError:
        response = make_response({'isLoggedIn':False})
        response.delete_cookie('token')        
        return response
    except:
        return jsonify({'isLoggedIn':False,'err':'Invalid'})
def login_required(f):
    @wraps(f)
    def isLoggedIn(*args, **kwargs):        
        token = None
        token = request.cookies.get('token')        
        if not token and 'Authorization' in request.headers:
            token = request.headers['Authorization'].replace('Bearer ','')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        try:            
            data = jwt.decode(token,JWT_SECRET,algorithms=['HS256'])
            current_user = mongo.db.users.find_one({'uname':data['uname']}) # type: ignore
            if not current_user:
                return jsonify({'error':'User not found'}),401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

    
        return f(current_user,*args, **kwargs)
    return isLoggedIn



# Voting
@app.get('/poll')
def get_all_poll():
    pipeline = [
        {'$project':
        {
            'question':1,
            'options':1,
            'voteCount': {'$map':{
                'input':'$options',
                'as':'option',
                'in':{
                    'option':'$option',
                    'count':{'$size':{'$filter':{
                        'input':'$votes',
                        'as':'vote',
                        'cond':{'$eq':['$$vote','$$option']}                    
                    }}}
                }
            }}
        }
            }
    ]
    polls = mongo.db.poll.aggregate(pipeline) # type: ignore    
    return jsonify(polls)

@app.get('/share/<string:pollid>')
def get_poll(pollid):
    pipeline = [
        {'$match': {'_id': ObjectId(pollid)}},
        {'$project':
        {
            'question':1,
            'options':1,
            'voteCount': {'$map':{
                'input':'$options',
                'as':'option',
                'in':{
                    'option':'$option',
                    'count':{'$size':{'$filter':{
                        'input':'$votes',
                        'as':'vote',
                        'cond':{'$eq':['$$vote','$$option']}                    
                    }}}
                }
            }}
        }
            }
    ]
    poll = mongo.db.poll.aggregate(pipeline) # type: ignore    
    return jsonify(poll)

@app.post('/vote/<string:pollid>')
def vote(pollid):
    data = request.get_json()
    option = data.get('option') if data else None
    if not option: return jsonify({"error":'Missing Option'}),400
    result = mongo.db.poll.update_one( # type: ignore
        {'_id': ObjectId(pollid)},
        {'$push': {'votes': option}}
    )
    if result.modified_count == 0:
        return jsonify({"error": "Poll not found"}), 404
    return jsonify({"msg": "Success"})


@app.get('/mypoll')
@login_required
def get_my_poll(current_user):
    
    pipeline = [
        {'$match': {'created_by': current_user['uname']}},
        {'$project':
        {
            'question':1,
            'options':1,
            'voteCount': {'$map':{
                'input':'$options',
                'as':'option',
                'in':{
                    'option':'$option',
                    'count':{'$size':{'$filter':{
                        'input':'$votes',
                        'as':'vote',
                        'cond':{'$eq':['$$vote','$$option']}                    
                    }}}
                }
            }}
        }
            }
    ]
    mypoll = mongo.db.poll.aggregate(pipeline) # type: ignore    
    return app.response_class(dumps(list(mypoll)), mimetype='application/json')
@app.post('/createpoll')
@login_required
def create_poll(current_user):
    data = request.get_json()
    try:
        mongo.db.poll.insert_one({ # type: ignore
            'created_by': current_user['uname'],
            'options':data.get('options'),
            'question':data.get('question'),
            'votes':[]
        })
        return jsonify({'msg':'Creating Poll Success'}),201        
    except:
        return jsonify({'error':'Creating poll failed'})

@app.delete('/poll/<string:pollid>')
@login_required
def delete_my_poll(current_user,pollid):
    try:
        mongo.db.poll.delete_one({'_id':ObjectId(pollid)}) # type: ignore
        return jsonify({'msg':'Delete Success'}),200
    except:
        return jsonify({'error':'Delete Failed'}),400
            
@app.put('/poll/<string:pollid>')
@login_required
def update_option(current_user,pollid):
    data = request.get_json()
    try:
        mongo.db.poll.update_one({'_id':ObjectId(pollid)}, # type: ignore
            {'$push':{'options':data.get('new_option'),'votes':data.get('new_option')}}
        )
        return jsonify({'msg':'Adding new option success'}),200
    except:
        return jsonify({'error':'Adding new option failed'}),400
    
if __name__ == '__main__':
    # app.run(debug=True)
    # app.run(host='localhost', port=5000)
    # gunicorn -w 4 -b 0.0.0.0:8000 app:app