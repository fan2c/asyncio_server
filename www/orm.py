# -*- coding: utf-8 -*-
'''
ORM
'''

import asyncio, logging

import aiomysql

import sys
logging.basicConfig(level=logging.INFO)

def log(sql, args=()):
    logging.info('SQL: %s' %sql)

# connect Database
@asyncio.coroutine
def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    global __pool
    __pool = yield from aiomysql.create_pool(
        host = kw.get('host', 'localhost'),
        port = kw.get('port', 3306),
        user = kw['user'],
        password = kw['password'],
        db = kw['db'],
        loop = loop
    )

@asyncio.coroutine
def destroy_pool():
    global __pool
    if __pool is not None:
        __pool.close()
        yield from __pool.wait_closed()


# Select
@asyncio.coroutine
def select(sql, args, size=None):
    log(sql, args)
    global __pool
    with(yield from __pool) as conn:
        cur = yield from conn.cursor(aiomysql.DictCursor)
        yield from cur.execute(sql.replace('?', '%s'), args or ())
        if size:
            rs = yield from cur.fetchmany(size)
        else:
            rs = yield from cur.fetchall()
        yield from cur.close()
        logging.info('rows returned: %s' %len(rs))
        return rs

# INSET, UPDATE, DELETE
@asyncio.coroutine
def execute(sql, args):
    log(sql)
    with(yield from __pool) as conn:
        try:
            cur = yield from conn.cursor()
            yield from cur.execute(sql.replace('?', '%s'), args)
            affected = cur.rowcount
            yield from cur.close()
        except BaseException as e:
            raise
        return affected

# insert into 'User' ('password', 'email', 'name', 'id') values (?, ?, ?, ?)
def create_args_string(num):
    lol=[]
    for n in range(num):
        lol.append('?')
    return (','.join(lol))


# define Field class
class Field(object):
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default
    def __str__(self):
        return '<%s, %s: %s>' % (self.__class__.__name__, self.column_type, self.name)


# extends Field
# define 5 kinds of  data types
class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)
class BooleanField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'Boolean', False, default)
class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'int', primary_key, default)
class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'float', primary_key, default)
class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)

# define the Metaclass of Model
class ModelMetaclass(type):
    # cls: 代表要__init__的类，此参数在实例化时由Python解释器自动提供(例如下文的User和Model)
    # bases: 代表继承父类的集合
    # attrs: 类的方法集合
    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s(table: %s)' % (name, tableName))
        mappings = dict()
        fields = []
        primaryKey = None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                if v.primary_key:
                    # 找到主键:
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)
        if not primaryKey:
            raise RuntimeError('Primary key not found.')
        for k in mappings.keys():
            attrs.pop(k)
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__mappings__'] = mappings # 保存属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey # 主键属性名
        attrs['__fields__'] = fields # 除主键外的属性名
        # 构造默认的SELECT, INSERT, UPDATE和DELETE语句:
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)

# define the base class
# extend dict
class Model(dict, metaclass=ModelMetaclass):

    def __init(self, **kw):
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError("'Model' object have no attribution: %s"% key)


    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)
        return value

# 不需要实例化，直接类名.方法名()来调用
    @classmethod
    @asyncio.coroutine
    def find(cls, primaryKey):
        ' find object by primary key. '
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [primaryKey], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    @classmethod
    @asyncio.coroutine
    def findAll(cls, **kw):
        rs = []
        if len(kw) == 0:
            rs = yield from select(cls.__select__, None)
        else:
            args=[]
            values=[]
            for k, v in kw.items():
                args.append('%s=?' % k )
                values.append(v)
            rs = yield from select('%s where %s ' % (cls.__select__,  ' and '.join(args)), values)
        return rs

    @asyncio.coroutine
    def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = yield from execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)

    @asyncio.coroutine
    def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = yield from execute(self.__update__, args)
        if rows != 1:
            logging.warning('failed to update record: affected rows: %s'%rows)








'''
# testing
if __name__=="__main__":
    class User(Model):
        id = IntegerField('id',primary_key=True)
        name = StringField('username')
        email = StringField('email')
        password = StringField('password')
    #创建异步事件的句柄
    loop = asyncio.get_event_loop()

    #创建实例
    @asyncio.coroutine
    def test():
        yield from create_pool(loop=loop,host='localhost', port=3306, user='root', password='root123', db='test')
        user = User(id=8, name='fantc', email='fantc@naver.com', password='12345678')
        yield from user.save()
        r = yield from User.find('11')
        print(r)
        r = yield from User.findAll()
        print(1, r)
        r = yield from User.findAll(id='12')
        print(2, r)
        yield from destroy_pool()

    loop.run_until_complete(test())
    loop.close()
    if loop.is_closed():
        sys.exit(0)

INFO:root:found model: User(table: User)
INFO:root:found mapping: id ==> <IntegerField, int: id>
INFO:root:found mapping: name ==> <StringField, varchar(100): username>
INFO:root:found mapping: email ==> <StringField, varchar(100): email>
INFO:root:found mapping: password ==> <StringField, varchar(100): password>
INFO:root:create database connection pool...
INFO:root:SQL: insert into `User` (`name`, `email`, `password`, `id`) values (?,?,?,?)
INFO:root:SQL: select `id`, `name`, `email`, `password` from `User` where `id`=?
INFO:root:rows returned: 0
None
INFO:root:SQL: select `id`, `name`, `email`, `password` from `User`
INFO:root:rows returned: 2
1 [{'id': 8, 'email': 'fantc@naver.com', 'name': 'fantc', 'password': '12345678'}, {'id': 8, 'email': 'fantc@naver.com', 'name': 'fantc', 'password': '12345678'}]
INFO:root:SQL: select `id`, `name`, `email`, `password` from `User` where id=?
INFO:root:rows returned: 0
2 ()
'''
