import sys
sys.path.insert(0, r'c:/Users/HomePC/kenya-population-analysis')
import src.pipeline as p
b = p.load_boundaries()
print('rows=', len(b))
print('counties=', b['county'].nunique())
print('columns=', b.columns.tolist())
print(b.head(3).to_string(index=False))
