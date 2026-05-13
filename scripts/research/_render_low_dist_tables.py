import json
strict = json.load(open('data/research/vnindex_low_dist_forward_returns_strict.json', 'r', encoding='utf-8'))
robust = json.load(open('data/research/vnindex_low_dist_forward_returns_robust.json', 'r', encoding='utf-8'))
last_close = strict['facts']['last_close']
print('LAST_CLOSE:', last_close)

def show(name, j, kind):
    print()
    print('=== ' + name + ' (' + kind + ') ===')
    print('  candidates=' + str(j['anchors']['candidates_total']) + '  sparse=' + str(j['anchors']['sparse_total']))
    print('  Horizon  n   mean%   med%  win%    p10%    p25%    p75%    p90%   |  meanPt  medPt  p10Pt  p25Pt  p75Pt  p90Pt')
    for h in (20,50,100,150,200):
        s = j[kind][str(h)+'d']
        if s['n']==0: continue
        m=s['mean']*100; md=s['median']*100; wr=s['win_rate']*100
        p10=s['p10']*100; p25=s['p25']*100; p75=s['p75']*100; p90=s['p90']*100
        mp=s['mean']*last_close; mdp=s['median']*last_close
        p10p=s['p10']*last_close; p25p=s['p25']*last_close; p75p=s['p75']*last_close; p90p=s['p90']*last_close
        print('  %4dd  %3d  %+6.2f  %+5.2f %5.1f  %+6.2f  %+6.2f  %+6.2f  %+6.2f   %+7.1f %+6.1f %+6.1f %+6.1f %+6.1f %+6.1f' % (h, s['n'], m, md, wr, p10, p25, p75, p90, mp, mdp, p10p, p25p, p75p, p90p))

show('STRICT 31TD <=1 dist (start 24/3)', strict, 'forward_returns_sparse')
show('ROBUST 32TD <=2 dist (start 23/3)', robust, 'forward_returns_sparse')
show('STRICT dense', strict, 'forward_returns_dense')
show('ROBUST dense', robust, 'forward_returns_dense')
