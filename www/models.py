# -*- coding: utf-8 -*-
'''
Models
'''
import time, uuid

from orm import Model, StringField, BooleanField, FloatField, TextField, IntegerField



class User(Model):
    __table__ = 'users'

    id = StringField(primary_key=True, ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl='varchar(50)')
    username = StringField(ddl='varchar(50)')
    admin = BooleanField()
    avatar = StringField(ddl='varchar(50)')
    created_at = FloatField(default=time.time)

class Post(Model):
    id = StringField(primary_key=True, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    content = TextField()
    created_at = FloatField(default=time.time)
