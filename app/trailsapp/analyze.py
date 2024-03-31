import numpy as np
import matplotlib as mpl
# mpl.use('agg')
import matplotlib.pylab as plt
import matplotlib.cm as cm
import png
import io
import base64
import traceback

import diskcache as dc
cache = dc.Cache('tmp-cache')

def d_(x, n=10):
    d_filter = np.zeros(n)
    d_filter[0] = 1
    d_filter[-1] = -1
    R = np.convolve(x, d_filter, mode='same')
    
    R[:1]=0
    R[-1:]=0
    
    return R

def speed_estim_for_grade(grade, lut_speed_grade, peak=(0.1, 0.9), plot=False):

    i_grade = np.abs(grade - lut_speed_grade[2][:-1]).argmin()

    dp = np.copy(lut_speed_grade[0][:,i_grade])
    
    cdp = np.cumsum(dp/np.sum(dp))
    
    #print(cdp)
    
    if plot:
        plt.figure()
        plt.plot(
            lut_speed_grade[1][:-1],
            cdp
        )
        plt.plot(
            lut_speed_grade[1][:-1],
            dp/np.sum(dp)*10
        )
        
        plt.axvline(np.sum(lut_speed_grade[1][:-1]*dp)/np.sum(dp))
    
    b1 = np.argmin(np.abs(cdp-peak[0]))
    b2 = np.argmin(np.abs(cdp-peak[1]))
    
    dp[:b1] = 0
    dp[b2:] = 0
    
    if plot:
        plt.plot(
            lut_speed_grade[1][:-1],
            dp/np.sum(dp)*10
        )
        
        plt.axvline(np.sum(lut_speed_grade[1][:-1]*dp)/np.sum(dp))
    

    return np.sum(lut_speed_grade[1][:-1]*dp)/np.sum(dp)

    #lut_speed_grade[2][i_grade], grade, lut_speed_grade[0][i_grade]

def load_model(version="v0"):
    # cache
    return np.load(open("lut_merged_prod.npy", "rb"), allow_pickle=True)
    
def extract_modes(grade, d_time, d_d3, altitude):
    N = 3

    g_m = d_time>0
    grade = grade[g_m]
    d_time = d_time[g_m]
    d_d3 = d_d3[g_m]
    altitude = altitude[g_m]

    asc = d_(altitude, 2)
    asc[asc<0] = 0
    desc = d_(altitude, 2)
    desc[desc>0] = 0

    # should also determine this by clustering
    # should also determine this by clustering
    m_route_run_steep = grade<-20.
    m_route_run_flat = (grade<8.) & (grade>-20.)
    m_route_walk = (grade>8.) & (grade<30.)
    m_route_steep = grade>30.

    S = {}

    # print(d_time)
    # print(d_time[d_time<0])

    for i, (n, mx) in enumerate([
        ("run flat", m_route_run_flat),
        ("walk up", m_route_walk),
        ("steep up", m_route_steep),
        ("down steep", m_route_run_steep),
        ("all", np.ones_like(m_route_run_steep)),
    ]):        
        print(f"{n:10s} "+
              f"\033[032m{np.sum(d_time[mx])/np.sum(d_time)*100:5.1f}%\033[0m time " +
              f"{np.sum(d_time[mx])/3600.:.2f} hr " +
              f"{np.sum(d_d3[mx])/1000.:.2f} km",
              f"{np.sum(d_(altitude, N)[mx])/(N-1):.2f} ",
             )
        rm = {}
        S[n.replace(" ", "_")] = rm
        rm['time_fraction_pc'] = np.sum(d_time[mx])/np.sum(d_time)*100
        rm['time_s'] = np.sum(d_time[mx])
        rm['distance_m'] = np.sum(d_d3[mx])
        rm['elevation_gain_m'] = np.sum(asc[mx])
        rm['elevation_loss_m'] = np.sum(desc[mx])
        rm['vam'] = rm['elevation_gain_m']/rm['time_s']*3600.
        rm['vdm'] = rm['elevation_loss_m']/rm['time_s']*3600.
        rm['kmh'] = rm['distance_m']/rm['time_s']*3600./1000.
        rm['grade_av'] = 100*(rm['elevation_gain_m'] / rm['distance_m'])
        rm['grade_min'] = np.nanmin(grade[mx]) if np.sum(mx)>0 else 0
        rm['grade_max'] = np.nanmax(grade[mx]) if np.sum(mx)>0 else 0
        rm['order'] = i

    return S


def analyze_route(route, plot=False, lut_merged=None):
    if lut_merged is None:
        lut_merged = load_model()

    d_N = 2
    N = 3

    route_points = route['route_points']

    d_route_d3 = np.array([0] + [a.distance_3d(b) for a,b in zip(route_points[:-1], route_points[1:])])
    route_d3 = np.cumsum(d_route_d3)

    route_lat = np.array([p.latitude for p in route_points])
    route_lon = np.array([p.longitude for p in route_points])
    route_altitude = np.array([p.elevation for p in route_points])
    route_grade = d_(route_altitude)/d_(route_d3, 10)*100.
    
    print(f"\033[31m{route['route_gpx'].name}\033[0m", route['type'], route['sub_type'])

    if plot:
        print("plotting")
        plt.figure()
        plt.title(route['route_gpx'].name)

        plt.scatter(
            route_lon,
            route_lat,
            c=cm.jet(route_grade/50.),
        )
        plt.xlabel("longitude")
        plt.ylabel("latitude")

        plt.grid()
    #plt.ylim([-50, 50])

    total_time_estim = 0
    total_time_model_estim = 0
    i = 0

    _ = estimate_track(d_route_d3, d_(route_altitude, 2), None, None, lut_merged, d_N)
    total_time_estim = _['total_time_estim']
    d_time_estims = np.array(_['d_time_estims'])

    total_time_alt_estim = 0
    
    print(f"total distance {np.sum(d_route_d3)/1000.:.2f} km")
    
    
    summary = {} 
    route['analysis'] = summary

    asc = d_(route_altitude, 2)
    asc[asc<0] = 0

    summary['cumulative_elevation_gain'] = np.sum(np.sum(d_(route_altitude, N)/(N-1)))
    summary['total_elevation_gain'] = np.sum(asc[asc>0])
    summary['elevation_min'] = np.min(route_altitude)
    summary['elevation_max'] = np.max(route_altitude)
    summary['elevation_diff'] = np.max(route_altitude) - np.min(route_altitude)
    summary['total_time_estimate_s'] = total_time_estim
    summary['total_time_alt_estimate_s'] = total_time_alt_estim

    print(f"cumulative elevation gain {summary['cumulative_elevation_gain']:.2f} m")
    print(f"total elevation gain {summary['total_elevation_gain']:.2f} m")
    print(f"total time {total_time_estim/3600.:.2f}")


    summary['modes'] = extract_modes(route_grade, d_time_estims, d_route_d3, route_altitude)

    summary['modes_string'] = ",".join([ "%.5lg"%m['time_fraction_pc'] for n, m in sorted(summary['modes'].items(), key=lambda x:x[1]['order']) if n is not "all"])
        
        
    if plot:
        plt.figure()
        plt.plot(
            np.cumsum(d_route_d3),
            route_altitude,            
        )
        plt.xlabel("distance [m]")
        plt.plot(
            np.cumsum(d_route_d3),
            np.cumsum(d_(route_altitude, N))/(N-1),
        )
        plt.grid()
                
    return summary
    

def pngbar(fractions):
    if fractions in cache:
        return cache[fractions]

    width = 100
    height = 5
    img = []

    print(fractions)
    fractions = np.concatenate([[0],np.cumsum([ f/np.sum(fractions) for f in fractions])])
    print(fractions)

    row = ()
    for x in range(width):
        a = fractions - x/width
        a[a <= 0] = 1
        i = np.argmin(a)
        px = tuple([int(c*255) for c in cm.jet(i/len(fractions))[:-1]])
        row = row + px

    #print(row)

    for y in range(height):
        img.append(row)

    f = io.BytesIO()
    w = png.Writer(width, height, greyscale=False)
    w.write(f, img)

    cache[fractions] = f.getvalue()
    return cache[fractions]

def analyze_activity(activity, lut_merged=None, onlycache=False):
    #if 'Snow' not in activity['name']:
    #    return

    cache_key = (activity["id"], "v0")
    if cache_key in cache:
        activity['analysis'] = cache[cache_key]
        print("\033[32min cache!\033[0m")
        return True
    if onlycache:
        return False


    d_N = 10

    if 'streams' not in activity:
        print("\033[31mno streams!\033[0m")
        return
        
    streams = activity['streams']
    
    

    try:
        distance = np.array(streams['distance']['data'])
        altitude = np.array(streams['altitude']['data'])
        ttime = np.array(streams['time']['data'])
        latlng = np.array(streams['latlng']['data'])
    except Exception as e:
        print("\033[31mno good data!\033[0m", e)
        traceback.print_exc()
        return
    
    cadence = None
    heartrate = None
    try:
        cadence = np.array(streams['cadence']['data'])*2.
        heartrate = np.array(streams['heartrate']['data'])
    except Exception as e:
        print("\033[31mno optional data!\033[0m", e)
    
    d_distance = d_(distance, d_N)
    d_altitude = d_(altitude, d_N)
    d_d3 = (d_distance**2 + d_altitude**2)**0.5
    d_time = d_(ttime, d_N)
    
    speed_kph = d_d3/d_time *3600./1000.
    vam = d_altitude/d_time    
    grade = d_altitude/d_d3*100.
    

    def dealias(x):
        mn = np.round(np.abs(x[x>0]).min(), 5)
        print("found step", mn)
        x += np.random.rand(altitude.shape[0])*mn - mn/2.
        
    if cadence is not None:
        dealias(cadence)
    dealias(d_altitude)
    dealias(d_distance)
    

    speed_kph = d_d3/d_time *3600./1000.
    vam = d_altitude/d_time*1000
    grade = d_altitude/d_d3*100.

    m = np.abs(d_altitude)<1000
    m &= np.abs(vam)<2000

    def p2d(x,y, x_bins, y_bins, mode='hist'):

        if mode == "scatter":
            plt.scatter(x,y,s=5)
        elif mode == 'hist':
            return plt.hist2d(x,y, bins=(
                    x_bins,
                    y_bins,
                )
            )
        elif mode == 'contour':
            h2, a,b  = np.histogram2d(x,y, bins=(
                    x_bins,
                    y_bins,
                )
            )

            plt.contourf(
                a[:-1],
                b[:-1],
                np.transpose(h2),
                #levels=np.logspace(np.log10(h2.max()/1000.), np.log10(h2.max()), 100)
                levels=np.linspace(0, h2.max(), 100)
            )


    for mode in 'hist',: #'contour':
        f, (ax1,ax2)= plt.subplots(1,2,figsize=(9,5))
        lut_speed_grade = p2d(
            speed_kph[m],
            #d_altitude[m]/d_time[m]*3600.,
            #60./(d_distance[m]/d_time[m]*3600./1000.),
            #d_distance[m]/d_time[m]*3600./1000.,
            #d_altitude[m]/d_time[m]*3600.,
            #d_altitude[m]/d_time[m]*3600,
            grade[m],
            mode = mode,
            x_bins = np.linspace(0, 15, 70),
            y_bins = np.linspace(-60, 60, 70),
            #y_bins = np.linspace(-2000, 2000, 70),
        )
        
        #luts.append(lut_speed_grade)
        
        plt.subplots_adjust(wspace=0)
        
        ax1.scatter(latlng[:,1], latlng[:,0], 
            #c=cm.jet(np.array(streams['velocity_smooth']['data'])/6.),
            c=cm.jet((
                np.array(d_altitude*3600)/(1000.)
                #np.array(streams['altitude']['data'])-320)/(600-320)
            ),
        ))
        
        plt.title(activity['name'])
        
    print("total time", (ttime[-1] - ttime[0])/3600., "hr")
    
    x_grade = np.linspace(-50,50)
    ax2.plot(
        [speed_estim_for_grade(x, lut_speed_grade, (0, 1.)) for x in x_grade],
        x_grade,
        c="k",
        lw=3,
    )

    if lut_merged is not None:
        ax2.plot(
            [speed_estim_for_grade(x, lut_merged, (0.3, 0.7)) for x in x_grade],
            x_grade,
            c="r",
            lw=3,
            ls=":"
        )
    
    if heartrate is not None:
        plt.figure()
        plt.hist2d(
            grade[m], 
            heartrate[m],
            bins=(np.linspace(-60,60,100), np.linspace(0,200,100)),
        )
        plt.axvline(8.)
    

    _ = estimate_track(d_d3, d_altitude, d_time, ttime, lut_speed_grade, d_N=d_N)
    total_time_estim=_['total_time_estim']
    sum_time=_['sum_time']
    
    _ = estimate_track(d_d3, d_altitude, d_time, ttime, lut_merged, d_N=d_N)
    total_time_model_estim=_['total_time_estim']

    print("total time estimate", total_time_estim/3600., "hr", "summed time", sum_time/3600., "hr")
    print("total time model estimate", total_time_model_estim/3600., "hr", "summed time", sum_time/3600., "hr")

    S = {}
    activity['analysis'] = S

    activity['analysis']['modes'] = extract_modes(grade, d_time/(d_N-1), d_d3/(d_N-1), altitude)
    activity['analysis']['modes_string'] = ",".join([ "%.5lg"%m['time_fraction_pc'] for n, m in sorted(activity['analysis']['modes'].items(), key=lambda x:x[1]['order']) if n is not "all"])

    S['total_time_estimate_s'] = total_time_estim
    S['total_time_model_estimate_s'] = total_time_model_estim
    S['summed_time_s'] = sum_time
    S['lut'] = lut_speed_grade

    buf = io.BytesIO()
    plt.savefig(buf, format='png')

    S['lut_png_b64'] = base64.b64encode(buf.getvalue())
    
    #print("total run fraction", np.sum(m_run)/m_run.shape[0])
        
    #break

    #ax=plt.gca()
    #ax2=plt.twiny()
    #ax2.set_xlim(60./np.array(ax.get_xlim()))

    #plt.xlabel("pace")
    #plt.ylabel("grade")
    #plt.ylabel("VAM")

    cache[cache_key] = activity['analysis']

def estimate_track(d_d3, d_altitude, d_time, ttime, lut, d_N):
    total_time_estim = 0
    sum_time = 0
    d_time_estims = []
    i = 0

    if d_time is None:
        d_time = np.zeros_like(d_d3)

    if ttime is None:
        ttime = np.zeros_like(d_d3)

    for d_d, d_a, d_t, _t in zip(d_d3, d_altitude, d_time, ttime):
        d_time_estims.append(0)
        i += 1
        if i<d_N+1: continue
        if i>len(d_time)-d_N-1: continue
        
        grade = d_a/d_d*100.
        
        d_time_estim = d_d/(speed_estim_for_grade(grade, lut)/3600.*1000)/(d_N-1)
        
        if not np.isnan(d_time_estim)and  not np.isinf(d_time_estim):
            total_time_estim += d_time_estim
            sum_time += d_t/(d_N-1)
            d_time_estims[-1] = d_time_estim

        #print("since", _t - ttime[0], "estim", total_time_estim, "sum", sum_time)
        #print("grade", grade, "speed", d_d/d_t*3.6, "estim speed", speed_estim_for_grade(grade, lut_speed_grade), "time estim", d_time_estim, "time spent", d_t)
        

    return dict(
                total_time_estim=total_time_estim,
                sum_time=sum_time,
                d_time_estims = d_time_estims,
            )
        

def produce_lut(gpx):    
    d_N = 10    
    
    route_points = list(gpx.tracks)[0].segments[0].points

    d_route_d3 = np.array([0] + [a.distance_3d(b) for a,b in zip(route_points[:-1], route_points[1:])])
    route_d3 = np.cumsum(d_route_d3)

    distance = route_d3
    altitude = np.array([p.elevation for p in route_points])
    ttime = np.array([p.time.timestamp() for p in route_points])
    latlng = np.array([(p.latitude, p.longitude) for p in route_points])
      
    d_distance = d_(distance, d_N)
    d_altitude = d_(altitude, d_N)
    d_d3 = (d_distance**2 + d_altitude**2)**0.5
    d_time = d_(ttime, d_N)
    
    speed_kph = d_d3/d_time *3600./1000.
    vam = d_altitude/d_time    
    grade = d_altitude/d_d3*100.
    

    def dealias(x):
        mn = np.round(np.abs(x[x>0]).min(), 5)
        print("found step", mn)
        x += np.random.rand(altitude.shape[0])*mn - mn/2.
        
    # dealias(cadence)
    dealias(d_altitude)
    dealias(d_distance)

    speed_kph = d_d3/d_time *3600./1000.
    vam = d_altitude/d_time*1000
    grade = d_altitude/d_d3*100.

    m = np.abs(d_altitude)<1000
    m &= np.abs(vam)<2000

    def p2d(x,y, x_bins, y_bins, mode='hist'):

        if mode == "scatter":
            plt.scatter(x,y,s=5)
        elif mode == 'hist':
            return plt.hist2d(x,y, bins=(
                    x_bins,
                    y_bins,
                )
            )
        elif mode == 'contour':
            h2, a,b  = np.histogram2d(x,y, bins=(
                    x_bins,
                    y_bins,
                )
            )

            plt.contourf(
                a[:-1],
                b[:-1],
                np.transpose(h2),
                #levels=np.logspace(np.log10(h2.max()/1000.), np.log10(h2.max()), 100)
                levels=np.linspace(0, h2.max(), 100)
            )


    # for mode in 'hist',: #'contour':
    f, (ax1,ax2)= plt.subplots(1,2,figsize=(9,5))
    lut_speed_grade = p2d(
        speed_kph[m],
        #d_altitude[m]/d_time[m]*3600.,
        #60./(d_distance[m]/d_time[m]*3600./1000.),
        #d_distance[m]/d_time[m]*3600./1000.,
        #d_altitude[m]/d_time[m]*3600.,
        #d_altitude[m]/d_time[m]*3600,
        grade[m],
        mode = 'hist',
        x_bins = np.linspace(0, 15, 70),
        y_bins = np.linspace(-60, 60, 70),
        #y_bins = np.linspace(-2000, 2000, 70),
    )
    
    lut_speed_grade
    
    plt.subplots_adjust(wspace=0)
    
    ax1.scatter(latlng[:,1], latlng[:,0], 
        #c=cm.jet(np.array(streams['velocity_smooth']['data'])/6.),
        c=cm.jet((
            np.array(d_altitude*3600)/(1000.)
            #np.array(streams['altitude']['data'])-320)/(600-320)
        ),
    ))
    
    # plt.title(activity['name'])
        
    print("total time", (ttime[-1] - ttime[0])/3600., "hr")
        

    # x_grade = np.linspace(-50,50)
    # ax2.plot(
    #     [speed_estim_for_grade(x, lut_merged, (0, 1.)) for x in x_grade],
    #     x_grade,
    #     c="k",
    #     lw=3,
    # )
    # ax2.plot(
    #     [speed_estim_for_grade(x, lut_merged, (0.3, 0.7)) for x in x_grade],
    #     x_grade,
    #     c="r",
    #     lw=3,
    #     ls=":"
    # )
    
    # plt.figure()
    # plt.hist2d(
    #     grade[m], 
    #     heartrate[m],
    #     bins=(100, 100),
    # )
    # plt.axvline(8.)
    

    
    # total_time_estim = 0
    # sum_time = 0
    # i = 0
    # for d_d, d_a, d_t, _t in zip(d_d3, d_altitude, d_time, ttime):
    #     i += 1
    #     if i<30: continue
    #     if i>len(d_time)-100: continue
        
    #     #print(d_d, d_a)
        
    #     grade = d_a/d_d*100.
        
    #     d_time_estim = d_d/(speed_estim_for_grade(grade, lut_merged)/3600.*1000)/(d_N-1)
        
    #     if not np.isnan(d_time_estim)and  not np.isinf(d_time_estim):
    #         total_time_estim += d_time_estim
    #         sum_time += d_t/(d_N-1)
                        
    #     #print("since", _t - ttime[0], "estim", total_time_estim, "sum", sum_time)
    #     #print("grade", grade, "speed", d_d/d_t*3.6, "estim speed", speed_estim_for_grade(grade, lut_speed_grade), "time estim", d_time_estim, "time spent", d_t)
        
        
        
    # print("total time estimate", total_time_estim/3600., "hr", "summed time", sum_time/3600., "hr")
    
    # print("total run fraction", np.sum(m_run)/m_run.shape[0])
        
    # #break

    # #ax=plt.gca()
    # #ax2=plt.twiny()
    # #ax2.set_xlim(60./np.array(ax.get_xlim()))

    # #plt.xlabel("pace")
    # #plt.ylabel("grade")
    # #plt.ylabel("VAM")
    return lut_speed_grade


def produce_merged_lut(gpxes, write=False):
    luts = []
    for gpx in gpxes:
        luts.append(produce_lut(gpx))
        
    lut_merged = np.sum([l[0] for l in luts], 0), luts[0][1], luts[0][2]

    if write:
        np.save(open("lut_merged.npy", "wb"), lut_merged)

    return lut_merged