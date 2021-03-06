#!/usr/bin/env python
# -*- coding:utf-8
"""
Author:  Hao Li
Email: howardleeh@gmail.com
Github: https://github.com/SAmmer0
Created: 2018/4/18
"""
from os.path import join, exists
import json
from collections import deque
import datetime as dt
import logging
from sys import stdout

from pitdata.const import CONFIG, METADATA_FILENAME, UPDATE_TIME_THRESHOLD, LOGGER_NAME, UPDATING_LOGGER
from pitdata.updater.loader import load_all
from pitdata.updater.order import DependencyTree
from pitdata.io import insert_data
from qrtconst import ENCODING
from tdtools import trans_date, get_calendar

# --------------------------------------------------------------------------------------------------
# 预处理
# 系统日志记录初始化
logger = logging.getLogger(LOGGER_NAME)
updating_logger = logging.getLogger(UPDATING_LOGGER)

# --------------------------------------------------------------------------------------------------
# 功能函数
def load_metadata(filename):
    '''
    从文件中加载并转换元数据，元数据的格式如下
    {rel_path: update_time}

    Parameter
    ---------
    filename: string
        元数据的名称，元数据写入到数据库的主文件夹下

    Return
    ------
    metadata: dict
        转换后的元数据，update_time为datetime类
    '''
    dbpath = CONFIG['db_path']
    file_path = join(dbpath, filename)
    if not exists(file_path):    # 不存在元数据文件，初始化
        return {}
    with open(file_path, 'r', encoding=ENCODING) as f:
        metadata = json.load(f)
    for d, v in metadata.items():
        metadata[d] = trans_date(v)
    return metadata

def dump_metadata(metadata, filename):
    '''
    将元数据导入到文件中

    Parameter
    ---------
    metadata: dict
        元数据
    filename: string
        元数据名称
    '''
    dbpath = CONFIG['db_path']
    file_path = join(dbpath, filename)
    tobe_dumped = {d: metadata[d].strftime('%Y-%m-%d')
                   for d in metadata}
    with open(file_path, 'w', encoding=ENCODING) as f:
        json.dump(tobe_dumped, f)


def update_single_data(data_msg, start_time, end_time, ut_meta):
    '''
    执行数据计算、存储和元数据更新工作

    Parameter
    ---------
    data_msg: dict
        load_all函数返回的数据字典中的值，具体格式为{'data_description': dd, 'rel_path': rel_path}
    start_time: datetime
        更新的起始时间(准确的数据时间，经过交易日调整)
    end_time: datetime
        更新的终止时间(准确的数据时间，经过交易日调整)
    ut_meta(inout): dict
        更新时间元数据(函数运行过程中会修改ut_meta中的数据)

    Return
    ------
    result: boolean
    '''
    dd = data_msg['data_description']
    update_func = dd.calc_method
    try:
        data = update_func(start_time, end_time)
    except Exception as e:
        # 此处添加日志记录
        logger.exception(e)
        return False
    result = insert_data(data, data_msg['rel_path'], dd.datatype)
    if result:    # 插入数据成功后更新元数据
        ut_meta[dd.name] = end_time
    return result


def is_dependency_updated(data_msg, ut_meta, end_time):
    '''
    检查是否所有的依赖项都已经更新完毕

    Parameter
    ---------
    data_msg: dict
        load_all函数返回的数据字典中的值，具体格式为{'data_description': dd, 'rel_path': rel_path}
    ut_meta: dict
        更新时间元数据
    end_time: datetime like
        最新的数据时间

    Return
    ------
    result: boolean
    '''
    dd = data_msg['data_description']
    if dd.dependency is None:    # 无依赖项
        return True
    for dep in dd.dependency:
        if ut_meta[dep] != end_time:
            return False
    return True

def is_test_data(dmsg):
    '''
    判断当前数据是否为处于测试中的数据

    Parameter
    ---------
    dmsg: dictionary
        格式为{'data_description': dd, 'rel_path': rel_path}

    Return
    ------
    result: boolean
        True表示处于测试中
    '''
    return dmsg['data_description'].in_test

def get_endtime():
    '''
    计算当前时间对应的数据结束时间

    Return
    ------
    end_time: datetime
        最新的更新结束时间(交易日)
    '''
    now = dt.datetime.now()
    if now.hour < UPDATE_TIME_THRESHOLD:
        now = now - dt.timedelta(1)    # 若当天还未到给定时间，往前推一个自然日，再计算交易日
    return get_calendar('stock.sse').latest_tradingday(now, 'PAST')

def update_all(show_progress=True):
    '''
    更新所有数据，直至所有数据更新完成或者达到最大循环次数

    Parameter
    ---------
    show_progress: boolean, default True
        是否显示更新进程

    Return
    ------
    result: boolean
    '''
    data_dict = load_all()
    ut_meta = load_metadata(METADATA_FILENAME)
    update_order = [d.name for d in DependencyTree(data_dict).generate_dependency_order()]
    end_time = get_endtime()
    default_start_time = trans_date(CONFIG['data_start_date'])
    update_result = True
    stdout_handler = None    # stdout处理函数占位
    try:
        if show_progress:    # 添加终端打印日志处理函数
            stdout_handler = logging.StreamHandler(stdout)
            formater = logging.Formatter("%(asctime)s: %(message)s", "%Y-%m-%d %H:%M:%S")
            stdout_handler.setFormatter(formater)
            updating_logger.addHandler(stdout_handler)

        for data_name in update_order:
            d_msg = data_dict[data_name]
            if is_test_data(d_msg):  # 不更新处于测试中的数据
                updating_logger.info('[data_name={dn}, description=\"Testing data will not be updated, ignored\"'.
                                     format(dn=data_name))
                continue
            if not is_dependency_updated(d_msg, ut_meta, end_time):    # 依赖项还未更新，则直接忽视(本次不进行更新)
                updating_logger.info('[data_name={dn}, description=\"Dependency has not been updated, ignored\"]'.
                                     format(dn=data_name))
                continue
            start_time = ut_meta.get(data_name, default_start_time)
            if start_time >= end_time:
                updating_logger.info('[data_name={dn}, description=\"Data has been updated, ignored\"]'.
                                     format(dn=data_name))
                continue
            result = update_single_data(d_msg, start_time, end_time, ut_meta)
            updating_logger.info('[data_name={dn}, start_time={st:%Y-%m-%d}, end_time={et:%Y-%m-%d}, result={res}]'.
                                 format(dn=data_name, st=start_time, et=end_time, res=result))
            if result:    # 更新成功之后，写入元数据
                dump_metadata(ut_meta, METADATA_FILENAME)
            else:
                update_result = False
    finally:
        if stdout_handler is not None:
            updating_logger.removeHandler(stdout_handler)
    return update_result
