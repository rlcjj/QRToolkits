#!/usr/bin/env python
# -*- coding:utf-8
"""
Author:  Hao Li
Email: howardleeh@gmail.com
Github: https://github.com/SAmmer0
Created: 2018/4/17
"""
from pitdata.const import DataType

class DataDescription(object):
    '''
    数据描述类，用于定义数据的基本特征

    Parameter
    ---------
    name: string
        数据名称，数据库中该名称应该唯一，非唯一的名称会导致报错
    calc_method: function
        计算数据的方法，形式为function(start_time, end_time)->pandas.DataFrame or pandas.Series，
        其中start_time和end_time为datetime like形式
    update_time: datetime like
        该数据描述对象的更新时间
    dep: list, default None
        依赖项，元素为其他的数据描述类的对象，默认为None表示无依赖项
    datatype: DataType or string
        数据格式，当前支持的有4中：DataType.PANEL_NUMERIC, DataType.PANEL_CHAR, DataType.TS_NUMERIC, DataType.TS_CHAR
        若类型为TS开头，则calc_method返回pandas.Series，反之则返回pandas.DataFrame
    desc: string, default ''
        数据相关描述
    '''
    def __init__(self, name, calc_method, update_time, datatype, dep=None, desc=''):
        self.name = name
        self.calc_method = calc_method
        self.update_time = update_time
        self.dependency = tuple(dep)
        if isinstance(datatype, str):
            datatype = DataType[datatype]
        self.datatype = datatype
        self.description = desc

    def __str__(self):
        res = '<DataDescription: name={name}, update_time={ut}, dependency={dep}, datatype={dt}, description={desc}>'
        return res.format(name=self.name, ut=self.update_time, dep=self.dependency,
                          dt=self.datatype, desc=self.description)

    def __repr__(self):
        res = 'DataDescription({name!r}, {fun!r}, {ut!r}, {dep!r}, {dt!r}, {desc!r})'
        return res.format(name=self.name, fun=self.calc_method, ut=self.update_time,
                          dep=self.update_time, dt=self.datatype, desc=self.description)
    def __eq__(self, other):
        return self.name == other.name
