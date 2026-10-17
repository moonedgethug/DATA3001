"""Pure, lossless assembly for the authorised per-drifter release.

This module does not clean, select, impute or delete observations/features.
"""
import json
import numpy as np
import pandas as pd
import pyarrow as pa


def unknown_reasons(regime, native_loss, evidence):
    r=np.asarray(regime);out=np.full(len(r),None,object)
    if not (r<0).any():return out
    if native_loss==0:reason='uncertain_from_start'
    elif evidence and evidence['decision']=='hold_unknown':reason='unresolved_boundary'
    elif evidence and evidence['decision']=='attached_at_end':reason='beyond_attached_evidence'
    else:raise ValueError('Unknown regime has no audited explanation')
    out[r<0]=reason
    return out


def assemble_track(frame, metadata, *, annotations=None, field_attributes=None, context=None):
    """Append typed native scalars and annotations, never overwrite a column."""
    if frame.columns.duplicated().any():raise ValueError('Duplicate prepared column names')
    table=pa.Table.from_pandas(frame,preserve_index=False)
    n=len(frame)
    for name,value in metadata.items():
        if name in table.column_names:raise ValueError(f'Metadata collision: {name}')
        scalar=np.asarray(value)
        if scalar.ndim:raise ValueError(f'Trajectory metadata is not scalar: {name}')
        if scalar.dtype.kind=='S':
            raw=bytes(scalar.item())
            table=table.append_column(name,pa.array([raw]*n,type=pa.binary()))
            try:readable=raw.decode('utf-8')
            except UnicodeDecodeError:readable=None
            companion=name+'_text'
            if companion in table.column_names or companion in metadata:
                raise ValueError(f'Decoded companion collision: {companion}')
            table=table.append_column(companion,pa.array([readable]*n,type=pa.string()))
        else:
            table=table.append_column(name,pa.array(np.repeat(scalar,n)))
    for name,value in (annotations or {}).items():
        if name in table.column_names:raise ValueError(f'Annotation collision: {name}')
        if isinstance(value,pa.Array):array=value
        elif np.isscalar(value) or value is None:array=pa.array([value]*n)
        else:array=pa.array(value)
        if len(array)!=n:raise ValueError(f'Annotation row count mismatch: {name}')
        table=table.append_column(name,array)
    fields=[]
    for field in table.schema:
        attrs=(field_attributes or {}).get(field.name)
        if attrs is not None:
            field=field.with_metadata({**(field.metadata or {}),
                b'source_attributes':json.dumps(attrs,sort_keys=True).encode()})
        fields.append(field)
    schema_metadata=dict(table.schema.metadata or {})
    schema_metadata[b'data3001']=json.dumps(context or {},sort_keys=True,allow_nan=False).encode()
    return pa.Table.from_arrays(table.columns,schema=pa.schema(fields,metadata=schema_metadata))
