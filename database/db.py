# -*- encoding: utf-8
'''
主数据库，用于管理和调用其他的数据库引擎

包含以下几个功能：
DBEngine: 数据库引擎抽象基类
Database: 主数据库
StoreFormat: 数据存储类型
ParamsParser: 通用参数类
'''
import enum
import os.path as path
from os import remove as os_remove
import warnings
import json

from pandas import to_datetime
from numpy import dtype as np_dtype

from database.const import DataClassification, DataValueCategory, DataFormatCategory, ENCODING
from database.hdf5Engine.dbcore import HDF5Engine
from database.jsonEngine.dbcore import JSONEngine

# ----------------------------------------------------------------------------------------------
# 函数
def strs2StoreFormat(t):
    '''
    将字符串元组解析成为StoreFormat
    主要是为了避免日后对StoreFormat的格式进行拓展导致需要修改的地方太多

    Parameter
    ---------
    t: tuple
        按照给定顺序设置的字符串类型元组

    Return
    ------
    out: StoreFormat
    '''
    if len(t) > 3:
        raise NotImplementedError
    fmt = []
    formater = [DataClassification, DataValueCategory, DataFormatCategory]
    max_length = len(formater) if len(formater) > len(t) else len(t)
    for idx in range(max_length):
        fmt.append(formater[idx][t[idx]])
    return StoreFormat.from_iterable(fmt)


# ----------------------------------------------------------------------------------------------
# 类
class StoreFormat(object):
    '''
    数据存储格式的分类
    提供方法如下:
    from_iterable: 使用类方法构造对象
    validate: 返回当前分类分类是否合理
    提供属性如下:
    level: int，分类的层级
    data: tuple，分类详情，所有分类必须是enum.Enum的子类

    Notes
    -----
    目前只支持三层分类，第一层为DataClassfication，第二层为DataValueCategory，第三层为DataFormatCategory
    '''
    def __init__(self):
        self._rule = {DataClassification.STRUCTURED: [DataValueCategory.CHAR, DataValueCategory.NUMERIC],
                      DataClassification.UNSTRUCTURED: [None],
                      DataValueCategory.CHAR: [DataFormatCategory.PANEL, DataFormatCategory.TIME_SERIES],
                      DataValueCategory.NUMERIC: [DataFormatCategory.PANEL, DataFormatCategory.TIME_SERIES],
                      None: [None]}
        self._data = None

    @classmethod
    def from_iterable(cls, iterable):
        '''
        使用可迭代对象构造对象

        Parameter
        ---------
        iterable: iterable
            可迭代对象，每个元素为enum.Enum的子类

        Return
        ------
        obj: StoreFormat
        '''
        obj = cls()
        data = list(iterable)
        for classfication in data:
            if not isinstance(classfication, enum.Enum):
                raise TypeError('Elements must bet the subtype of enum.Enum')
        obj._data = tuple(data)
        return obj

    def validate(self):
        '''
        验证当前分类数据是否符合规则

        Return
        ------
        validated: boolean
            若符合规则，返回True，反之返回False
        '''
        last_cate = None
        rule = self._rule
        for cate in self._data:
            if last_cate is None:
                last_cate = cate
                continue
            if cate not in rule[last_cate]:
                return False
            last_cate = cate
        return True

    def to_strtuple(self):
        '''
        将各个分类详情对象转化为字符串形式

        Return
        ------
        out: tuple
            每个元素为按照顺序排列的分类对象的字符串形式
        '''
        out = []
        for c in self._data:
            out.append(c.name)
        return out

    def __eq__(self, other):
        for cate1, cate2 in zip(self, other):
            if cate1 != cate2:
                return False
            return True

    def __iter__(self):
        return iter(self._data)

    @property
    def data(self):
        return self._data

    @property
    def level(self):
        return len(self._data)

    def __getitem__(self, level):
        '''
        获取给定level的分类值

        Parameter
        ---------
        level: int
            所需要获取的分类的等级，0表示第一级，1表示第二级，...，以此类推

        Return
        ------
        out: enum.Enum
        '''
        return self._data[level]


class ParamsParser(object):
    '''
    参数解析类，用于对传入数据库引擎的数据进行包装

    该类提供一下方法:
    from_dict: 类方法，从参数字典中对对象进行初始化
    get_engine: 通过定义的规则获取对应的数据引擎
    parse_relpath: 将相对路径解析为绝对路径
    '''
    def __init__(self):
        self._main_path = None
        self._start_time = None
        self._end_time = None
        self._engine_map_rule = {(DataClassification.STRUCTURED, DataValueCategory.NUMERIC, DataFormatCategory.PANEL): HDF5Engine,
                                 (DataClassification.STRUCTURED, DataValueCategory.NUMERIC, DataFormatCategory.TIME_SERIES): HDF5Engine,
                                 (DataClassification.STRUCTURED, DataValueCategory.CHAR, DataFormatCategory.PANEL): JSONEngine,
                                 (DataClassification.STRUCTURED, DataValueCategory.CHAR, DataFormatCategory.TIME_SERIES): JSONEngine}
        # 参数组合校验字典，键为(start_time is None, end_time is None)，值为对应的存储类型
        self._validation_rule = {(False, False): StoreFormat.from_iterable((DataClassification.STRUCTURED, )),
                                 (True, False): StoreFormat.from_iterable((DataClassification.STRUCTURED,)),
                                 (False, True): StoreFormat.from_iterable((DataClassification.STRUCTURED,)),
                                 (True, True): StoreFormat.from_iterable((DataClassification.UNSTRUCTURED,))}
        self._store_fmt = None
        self._rel_path = None
        self._absolute_path = None
        self._dtype = None

    @classmethod
    def from_dict(cls, db_path, params):
        '''
        使用字典类型的参数数据构造参数解析类

        Parameter
        ---------
        db_path: string
            数据库的绝对路径
        params: dict
            字典类型的参数，参数域包含['rel_path'(必须)(string), 'start_time'(datetime),
            'end_time'(datetime), 'store_fmt'(StoreFormat), 'dtype'(numpy.dtype)]

        Return
        ------
        obj: ParamsParser
        '''
        obj = cls()
        obj._main_path = db_path
        obj._start_time = params.get('start_time', None)
        if obj._start_time is not None:
            obj._start_time = to_datetime(obj._start_time)
        obj._end_time = params.get('end_time', None)
        if obj._end_time is not None:
            obj._end_time = to_datetime(obj._end_time)
        obj._rel_path = params['rel_path']
        obj._store_fmt = params.get('store_fmt', None)
        if obj._store_fmt is not None:
            obj._store_fmt = StoreFormat.from_iterable(obj._store_fmt)
        obj._dtype = params.get('dtype', None)
        if obj._dtype is not None:
            obj._dtype = np_dtype(obj._dtype)
        if not obj.store_fmt.validate():
            raise ValueError("Invalid parameter group!")
        return obj

    def get_engine(self):
        '''
        获取对应的数据库引擎
        '''
        return self._engine_map_rule[self._store_fmt.data]

    def set_absolute_path(self, abs_path):
        '''
        设置数据的绝对路径，路径的格式由设置的数据引擎规定，该方法仅由数据引擎调用，与该方法配对
        的有absolute_path只读属性，用于获取设置的absolute_path，将操作设置为方法是为了强调该方法仅
        能由数据引擎使用设置成descriptor可能会误导

        Parameter
        ---------
        abs_path: string
            由数据引擎自行解析的绝对路径
        '''
        self._absolute_path = abs_path


    @property
    def start_time(self):
        return self._start_time

    @property
    def end_time(self):
        return self._end_time

    @property
    def main_path(self):
        return self._main_path

    @property
    def rel_path(self):
        return self._rel_path

    @property
    def absolute_path(self):
        return self._absolute_path

    @property
    def store_fmt(self):
        return self._store_fmt

    @property
    def dtype(self):
        return self._dtype


class Database(object):
    '''
    主数据库接口类，用于处理与外界的交互
    目前支持以下方法:
    query: 获取请求的数据
    insert: 将数据存储到本地
    remove_data: 将给定路径的数据删除
    move_to: 将给定的数据移动到其他位置

    Parameter
    ---------
    db_path: string
        数据的存储路径
    '''
    def __init__(self, db_path):
        self._main_path = db_path

    def query(self, rel_path, store_fmt, start_time=None, end_time=None):
        '''
        查询数据接口

        Parameter
        ---------
        rel_path: string
            该数据在数据库中的相对路径，路径格式为db.sub_dir.sub_dir.sub_data
        store_fmt: StoreFormat or iterable
            数据存储格式分类
        start_time: datetime like
            数据开始时间(可选)，若请求的是面板数据的某个时间点的横截面数据，该参数不能为None，
            而end_time参数需要为None
        end_time: datetime like
            数据结束时间(可选)

        Return
        ------
        out: pandas.Series, pandas.DataFrame or object
        '''
        params = ParamsParser.from_dict(self._main_path, {'rel_path': rel_path,
                                                        'store_fmt': store_fmt,
                                                        'start_time': start_time,
                                                        'end_time': end_time})
        # 时间参数校验规则，键为(start_time is None, end_time is None)，值为对应的数据结构分类
        validation_rule = {(True, True): DataClassification.UNSTRUCTURED,
                           (False, False): DataClassification.STRUCTURED,
                           (False, True): DataClassification.STRUCTURED,
                           (True, False): None}
        time_flag = (start_time is None, end_time is None)
        vclassification = validation_rule[time_flag]
        if vclassification is None or vclassification != params.store_fmt[0]:
            raise ValueError('Invalid parameter group in database query!')
        engine = params.get_engine()
        data = engine.query(params)
        return data

    def insert(self, data, rel_path, store_fmt, dtype=None):
        '''
        存储数据接口

        Parameter
        ---------
        data: pandas.Series, pandas.DataFrame or object
            需要插入的数据
        rel_path: string
            数据的相对路径
        store_fmt: StoreFormat or iterable
            数据存储格式分类
        dtype: numpy.dtype like, default None
            数据存储类型，目前仅数值型数据需要提供该参数
        Return
        ------
        issuccess: boolean
            是否成功插入数据，True表示成功
        '''
        params = ParamsParser.from_dict(self._main_path, {'rel_path': rel_path,
                                                        'store_fmt': store_fmt,
                                                        'dtype': dtype})
        engine = params.get_engine()
        issuccess = engine.insert(data, params)
        return issuccess

    def remove_data(self, rel_path, store_fmt):
        '''
        将给定路径的数据删除

        Parameter
        ---------
        rel_path: string
            数据的相对路径
        store_fmt: StoreFormat
            数据存储方式分类

        Return
        ------
        issuccess: boolean
        '''
        params = ParamsParser.from_dict(self._main_path, {'rel_path': rel_path,
                                                        'store_fmt': store_fmt})
        engine = params.get_engine()
        issuccess = engine.remove_data(params)
        return issuccess


    def move_to(self, source_rel_path, dest_rel_path, store_fmt):
        '''
        将数据有原路径移动到新的路径下

        source_rel_path: string
            原存储位置的相对路径
        dest_rel_path: string
            目标存储位置的相对路径
        store_fmt: StoreFormat
            数据存储方式分类

        Return
        ------
        issuccess: boolean
        '''
        src_params = ParamsParser.from_dict(self._main_path, {'rel_path': source_rel_path,
                                                            'store_fmt': store_fmt})
        dest_params = ParamsParser.from_dict(self._main_path, {'rel_path': dest_rel_path,
                                                             'store_fmt': store_fmt})
        engine = src_params.get_engine()
        issuccess = engine.move_to(src_params, dest_params)
        return issuccess

    def find_data(self, name):
        '''
        查找给定数据或者数据集合名下的所有数据信息

        Parameter
        ---------
        name: string
            数据或者数据集合的名称

        Return
        ------
        out: list
            元素为字典形式，格式为{'rel_path': rel_path, 'store_fmt': store_fmt}
        '''
        pass

    def _load_meta(self):
        '''
        加载该数据库的元数据
        '''
        pass

    def _find(self, name, match_func):
        '''
        具体实现数据或者数据集合名查找的函数

        Parameter
        ---------
        name: string
            数据或者数据集合的名称
        match_func: callable
            判断两个名字是否相匹配的函数，格式签名为match_func(name, node_name)->boolean

        Return
        ------
        node: DataNode
            查找到的数据节点，若未找到，返回None
        '''
        passs

    @staticmethod
    def precisely_match(name, node_name):
        '''
        精确查找函数，即只有两个字符串相等才行

        Parameter
        ---------
        name: string
        node_name: string

        Return
        ------
        result: boolean
        '''
        pass

    def _updat_meta(self):
        '''
        依据操作更新数据文件树，并且将更新后的结构写入到元数据中
        '''
        pass


class DataNode(object):
    '''
    文件结构树节点类，用于标识数据库中各个数据文件(夹)之间的包含关系，其中根节点的parent为None

    Parameter
    ---------
    node_name: string
        当前节点名称，即数据文件的名称
    store_fmt: StoreFormat, default None
        仅叶子节点为非空
    '''
    def __init__(self, node_name, store_fmt=None):
        self._node_name = node_name
        self._store_fmt = store_fmt
        self._children = {}
        self._parent = None

    @classmethod
    def init_from_meta(cls, meta_data):
        '''
        从存储有数据文件结构的文件中对数进行初始化，目前使用BFS算法

        Parameter
        ---------
        meta_data: dict
            字典的形式如下:
            {
                "node_name": db_name,
                "children": [
                    {"node_name": folder1,
                    "children": [{"node_name": data11, "store_fmt": store_fmt}, {}, ...]},
                    {"node_name": folder2,
                    "children": [{}, {}, ...]},
                    ...
                ]
            }
            只有叶子节点没有children键

        Return
        ------
        obj: DataNode
            存储有当前数据的节点
        '''
        if 'children' in meta_data:   # 表示当前不是叶子节点
            obj = cls(meta_data['node_name'])
            for child_meta in meta_data['children']:
                child_obj = cls.init_from_meta(child_meta)
                obj.add_child(child_obj)
            return obj
        else:   # 叶子节点
            obj = cls(meta_data['node_name'], strs2StoreFormat(meta_data['store_fmt']))
            return obj


    def add_child(self, child):
        '''
        向该节点添加直接连接的子节点，并且将子节点的母节点设置为当前节点

        Parameter
        ---------
        child: DataNode
        '''
        child._parent = self
        self._children[child.node_name] = child

    def delete_child(self, child):
        '''
        将给定名称的(直接连接的)节点从该节点的子节点中删除，同时也将子节点的母节点重置为None

        Parameter
        ---------
        child: string
            子节点的节点名称，即node_name

        Return
        ------
        result: boolean
        '''
        if not self.has_child(child):
            warnings.warn("Delete a child which does not exist!", RuntimeWarning)
            return False
        del self._children[child]

    def has_child(self, child):
        '''
        判断给定的节点名称是否是当前节点的直接连接的子节点

        Parameter
        ---------
        child: string
            子节点名称

        Return
        ------
        result: boolean
        '''
        return child in self._children

    def to_dict(self):
        '''
        将该节点的数据以字典的形式导出

        Return
        ------
        out: dict
            字典的形式如下:
            {
                "node_name": db_name,
                "children": [
                    {"node_name": folder1,
                    "children": [{"node_name": data11, "store_fmt": store_fmt}, {}, ...]},
                    {"node_name": folder2,
                    "children": [{}, {}, ...]},
                    ...
                ]
            }
        '''
        out = {}
        out['node_name'] = self._node_name
        if self.is_leaf:
            out['store_fmt'] = list(self._store_fmt.to_strtuple())
            return out
        else:
            children_list = []
            for child in self._children.values():
                children_list.append(child.to_dict())
            out['children'] = children_list
            return out

    @property
    def node_name(self):
        return self._node_name

    @property
    def children(self):
        return self._children

    @property
    def parent(self):
        return self._parent

    @property
    def store_fmt(self):
        return self._store_fmt

    @property
    def is_leaf(self):
        return len(self._children) == 0

