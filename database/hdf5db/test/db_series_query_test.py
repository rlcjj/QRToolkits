#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2018-01-17 15:08:01
# @Author  : Hao Li (howardlee_h@outlook.com)
# @Link    : https://github.com/SAmmer0
# @Version : $Id$

from database.hdf5db.dbcore import *

start_time = '2017-03-01'
end_time = '2017-12-30'

db_path = r'C:\Users\c\Desktop\test\test_series.h5'
db = DBConnector.init_from_file(db_path)
data = db.query(start_time, end_time)
