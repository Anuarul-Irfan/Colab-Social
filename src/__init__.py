from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
app=Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = 'sqlite:///C:\\Users\\USER\\Downloads\\Forum.db'
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"]=False
app.config["SECRET_KEY"]=os.urandom(32)
app.config["DEBUG"]=True
db=SQLAlchemy(app)
from src import routes
