import sys, os, sqlite3, json

con = sqlite3.connect(r'C:\Users\ADMIN\Documents\MELODYX\melodyx.db')
con.row_factory = sqlite3.Row
cur = con.cursor()

row_an = cur.execute('SELECT * FROM analyses WHERE id = ?', ('an_9b2673209489',)).fetchone()
print('Analysis row exists:', bool(row_an))
if row_an:
    print('Analysis:', dict(row_an))

row_res = cur.execute('SELECT * FROM analysis_results WHERE analysis_id = ?', ('an_9b2673209489',)).fetchone()
print('Result row exists:', bool(row_res))
if row_res:
    res = json.loads(row_res['result_json'])
    music = res.get('music', {})
    notes = music.get('notes', [])
    measures = music.get('measures', [])
    tempo = music.get('tempo_bpm', {}).get('value')
    key = music.get('key', {}).get('value')
    time_sig = music.get('time_signature', {}).get('value')
    chords = music.get('chords', [])
    print(f'Tempo: {tempo}, Key: {key}, TimeSig: {time_sig}')
    print(f'Total notes: {len(notes)}, Total measures: {len(measures)}, Total chords: {len(chords)}')
    for n in notes[:5]:
        print('  note:', n.get('name'), 'pitch:', n.get('pitch'), 'start:', round(n.get('start', 0), 2), 'hand:', n.get('hand'))

