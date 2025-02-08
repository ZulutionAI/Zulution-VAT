from pathlib import Path
from collections import OrderedDict

import copy
import json

# anno_path = Path('../网易伏羲有灵众包/2月8日沟通/检查--试标1_副本.json')
# anno_path = Path('../玛达电影数据标注/2月8日沟通/试标完成/检查--20-1_副本.json')
anno_path = Path('../玛达电影数据标注/2月8日沟通/试标完成/检查--20-3_副本.json')

# load
with open(anno_path, 'r', encoding='utf-8') as f:
    anno = json.load(f)

# convert
DEFAULT_METAINFO_KEY = "<application:meta-info>"
APPLICATION_METAINFO = None
new_anno = OrderedDict()

for key, value in anno.items():
    if key == DEFAULT_METAINFO_KEY:
        APPLICATION_METAINFO = copy.deepcopy(value)
        continue
    checksum = value['checksum']
    new_anno[checksum] = {
        'filepath': key,
        **value,
    }

# save
with open(anno_path.with_suffix('.new.json'), 'w', encoding='utf-8') as f:
    data = {
        DEFAULT_METAINFO_KEY: APPLICATION_METAINFO,
        **new_anno,
    }
    json.dump(data, f, indent=2)

print(f"Converted {len(new_anno)} annotations")
