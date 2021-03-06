#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2018-01-17 14:51:29
# @Author  : Hao Li (howardlee_h@outlook.com)
# @Link    : https://github.com/SAmmer0
# @Version : $Id$

import numpy as np

from database.hdf5Engine.dbcore import HDF5Engine
from database.db import ParamsParser
from database.const import DataClassification, DataValueCategory, DataFormatCategory
from fmanager import query

start_time = '2017-01-01'
end_time = '2018-02-01'


db_path = r'C:\Users\c\Desktop\test'
data = HDF5Engine.query(ParamsParser.from_dict(db_path, {"rel_path": 'test', 
                                                  'start_time': start_time,
                                                  'end_time': end_time,
                                                  "store_fmt": (DataClassification.STRUCTURED, DataValueCategory.NUMERIC, DataFormatCategory.PANEL)}))
fm_data = query('CLOSE', (start_time, end_time))
data = data.fillna(-10000)
fm_data = fm_data.fillna(-10000)
print(np.all(np.all(data == fm_data, axis=1)))
