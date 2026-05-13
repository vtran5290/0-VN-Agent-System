import json
strict = json.load(open('data/research/vnindex_low_dist_forward_returns_ex_vin_strict.json', 'r', encoding='utf-8'))
robust = json.load(open('data/research/vnindex_low_dist_forward_returns_ex_vin_robust.json', 'r', encoding='utf-8'))
last_close_ex = strict['facts']['last_close_ex_vin']
last_close_full = strict['facts']['last_close_full']
print('LAST_CLOSE_FULL:', last_close_full)
print('LAST_CLOSE_EX_VIN:', last_close_ex)
print('LAST_W_VIN:', strict['facts']['last_w_VIN'])

def show(name, j, kind, base):
    print()
    print('=== ' + name + ' (' + kind + ') ===')
    print('  candidates=' + str(j['anchors']['candidates_total']) + '  sparse=' + str(j['anchors']['sparse_total']))
    print('  Horizon  n   mean   med  win    p10    p25    p75    p90   |  meanPt  medPt  p10Pt  p25Pt  p75Pt  p90Pt   base=' + ('%.2f' % base))
    for h in (20,50,100,150,200):
        s = j[kind][str(h)+'d']
        if s['n']==0: continue
        m=s['mean']*100; md=s['median']*100; wr=s['win_rate']*100
        p10=s['p10']*100; p25=s['p25']*100; p75=s['p75']*100; p90=s['p90']*100
        mp=s['mean']*base; mdp=s['median']*base
        p10p=s['p10']*base; p25p=s['p25']*base; p75p=s['p75']*base; p90p=s['p90']*base
        print('  %4dd  %3d  %+6.2f  %+5.2f %5.1f  %+6.2f  %+6.2f  %+6.2f  %+6.2f   %+7.1f %+6.1f %+6.1f %+6.1f %+6.1f %+6.1f' % (h, s['n'], m, md, wr, p10, p25, p75, p90, mp, mdp, p10p, p25p, p75p, p90p))

print()
print('### EX-VIN ANCHOR LIST (strict) ###')
print(strict['facts']['current_window_ex_vin'])

show('STRICT 31TD <=1 dist on EX-VIN (start 24/3)', strict, 'forward_returns_sparse_ex_vin', last_close_ex)
show('FULL VNINDEX returns at SAME ex-VIN strict anchors', strict, 'forward_returns_full_at_same_anchors', last_close_full)
show('ROBUST 32TD <=2 dist on EX-VIN (start 23/3)', robust, 'forward_returns_sparse_ex_vin', robust['facts']['last_close_ex_vin'])
show('FULL VNINDEX returns at SAME ex-VIN robust anchors', robust, 'forward_returns_full_at_same_anchors', robust['facts']['last_close_full'])
