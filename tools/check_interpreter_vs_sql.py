"""Проверка: интерпретатор выражений (Python, паттерн «Интерпретатор») и хранимая функция EVAL_FUNCTION (PostgreSQL)
дают одинаковые результаты. Для каждого типового изделия 40 случайных наборов значений параметров:
результат каждого ограничения из CHECK_CONSTRAINTS сравнивается с /cfg/expressions/preview, цена – с формулой цены.
Запуск при работающем сервере: python tools/check_interpreter_vs_sql.py [http://localhost:8000]"""
import json, random, urllib.request
import sys
B = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000'
def call(m, path, body=None):
    r=urllib.request.Request(B+path, method=m, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type':'application/json'})
    try: return json.load(urllib.request.urlopen(r))
    except urllib.error.HTTPError as e: return {'error': json.load(e)}
random.seed(1); bad=0; n=0
for t in call('GET','/cfg/templates'):
    card=call('GET',f"/cfg/templates/{t['id']}")
    ps=card['параметры_конфигурации']
    for _ in range(40):
        vals={}
        for p in ps:
            vals[str(p['id'])]= random.choice(p['значения'])['id'] if p['тип']=='ENUM' else random.randint(int(p['мин'] or 1), int(p['макс'] or 20))
        chk=call('POST',f"/cfg/templates/{t['id']}/check",{'значения':vals})
        sql={r['наименование']:r['результат'] for r in chk['проверки'] if r['вид']=='ОГРАНИЧЕНИЕ'}
        for c in card['ограничения']:
            py=call('POST','/cfg/expressions/preview',{'выражение':c['текст'],'изделие_id':t['id'],'значения':vals})
            n+=1
            if py.get('значение')!=sql[c['наименование']]: bad+=1; print('MISMATCH',c['текст'],vals,py,sql[c['наименование']])
        if chk['допустимо']:
            py=call('POST','/cfg/expressions/preview',{'выражение':card['формула_цены']['текст'],'изделие_id':t['id'],'значения':vals})
            n+=1
            if abs(round(py['значение'],2)-chk['цена'])>0.006: bad+=1; print('PRICE',vals,py['значение'],chk['цена'])
print('checked',n,'mismatches',bad)
