# -*- coding: utf-8 -*-
'''
Models
'''
import time, uuid

from orm import Model, StringField, BooleanField, FloatField, TextField, IntegerField



class User(Model):
    __table__ = 'users'
    
    id = StringField(primary_key=True, default=, ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(50)')
    created_at = FloatField(default=time.time)
