"""Decode official small-window SST responses without mutating source objects."""
import numpy as np
import pandas as pd


def decode_grid(payload, day):
    table=payload['table']
    if table['columnNames']!=['time','latitude','longitude','analysed_sst']:
        raise ValueError('Unexpected source columns')
    if table['columnUnits']!=['UTC','degrees_north','degrees_east','degree_C']:
        raise ValueError('Unexpected source units')
    frame=pd.DataFrame(table['rows'],columns=table['columnNames'])
    expected=pd.to_datetime(day,unit='D',utc=True)+pd.Timedelta(hours=12)
    if frame.empty or not pd.to_datetime(frame.time,utc=True).eq(expected).all():
        raise ValueError('Source daily timestamp does not match request')
    if frame.duplicated(['latitude','longitude']).any():
        raise ValueError('Duplicate source coordinate')
    matrix=frame.pivot(index='latitude',columns='longitude',values='analysed_sst').astype(float)
    if len(matrix)*len(matrix.columns)!=len(frame):
        raise ValueError('Incomplete source rectangle')
    # Pandas copy-on-write may expose a read-only NumPy view. The validity mask
    # must operate on our own array, leaving the received source data untouched.
    data=matrix.to_numpy(copy=True)
    data[(data < -2)|(data > 50)]=np.nan
    return matrix.columns.to_numpy(float),matrix.index.to_numpy(float),data
