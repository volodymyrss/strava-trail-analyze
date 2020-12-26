import numpy as np
import matplotlib as mpl
mpl.use('agg')
import matplotlib.pylab as plt
import matplotlib.cm as cm

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
    

def analyze_route(route, plot=False):
    lut_merged = np.load(open("lut_merged.npy", "rb"), allow_pickle=True)
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
        plt.figure()
        plt.title(route['route_gpx'].name)

        plt.scatter(
            route_lon,
            route_lat,
            c=cm.jet(route_grade/50.),
        )

        plt.grid()
    #plt.ylim([-50, 50])

    total_time_estim = 0
    i = 0
    d_time_estims = []
    for d_d, d_a in zip(d_route_d3, d_(route_altitude, 2)):
        d_time_estims.append(0)
        
        i += 1
        if i<d_N +1: continue
        if i>len(route_d3)-d_N -1: continue

        grade = d_a/d_d*100.

        estim_speed_ms = (speed_estim_for_grade(grade, lut_merged)/3600.*1000)
        d_time_estim = d_d/(estim_speed_ms)/(d_N-1)

        if not np.isnan(d_time_estim) and not np.isinf(d_time_estim):
            total_time_estim += d_time_estim
            #sum_time += d_t/(d_N-1)
            d_time_estims[-1] = d_time_estim

        #print("since", _t - ttime[0], "estim", total_time_estim, "sum", sum_time)
        #print(f"dd {d_d:.2f} {d_a:.2f} grade {grade:.2f} estim speed {estim_speed_ms*3.6:.2f}, dtime {d_time_estim:.3f} total time {total_time_estim/3600.:.2f}")

    d_time_estims=np.array(d_time_estims)
    
    print(f"total distance {np.sum(d_route_d3)/1000.:.2f} km (strava {route['distance']/1000.:.2f})")
    
    asc = d_(route_altitude, 2)
    
    summary = {} 
    route['analysis'] = summary

    summary['cumulative_elevation_gain'] = np.sum(np.sum(d_(route_altitude, N)/(N-1)))
    summary['total_elevation_gain'] = np.sum(asc[asc>0])
    summary['elevation_min'] = np.min(route_altitude)
    summary['elevation_max'] = np.max(route_altitude)
    summary['elevation_diff'] = np.max(route_altitude) - np.min(route_altitude)
    summary['total_time_estimate_s'] = total_time_estim

    print(f"cumulative elevation gain {summary['cumulative_elevation_gain']:.2f} m (strava {route['elevation_gain']:.2f})")
    print(f"total elevation gain {summary['total_elevation_gain']:.2f} m (strava {route['elevation_gain']:.2f})")
    print(f"total time {total_time_estim/3600.:.2f} strava estim {route['estimated_moving_time']/3600.:.2f}")


    m_route_run_steep = route_grade<-20.
    m_route_run_flat = (route_grade<8.) & (route_grade>-20.)
    m_route_walk = route_grade>8.
    m_route_steep = route_grade>30.

    summary['modes'] = {}

    for n, mx in [
        ("down steep", m_route_run_steep),
        ("run flat", m_route_run_flat),
        ("walk up", m_route_walk),
        ("steep up", m_route_steep),
    ]:        
        print(f"{n:10s} "+
              f"\033[032m{np.sum(d_time_estims[mx])/np.sum(d_time_estims)*100:5.1f}%\033[0m time " +
              f"{np.sum(d_time_estims[mx])/3600.:.2f} hr " +
              f"{np.sum(d_route_d3[mx])/1000.:.2f} km",
              f"{np.sum(d_(route_altitude, N)[mx])/(N-1):.2f} vm",
             )
        rm = {}
        summary['modes'][n.replace(" ", "_")] = rm
        rm['time_fraction_pc'] = np.sum(d_time_estims[mx])/np.sum(d_time_estims)*100
        rm['time_s'] = np.sum(d_time_estims[mx])
        rm['distance_m'] = np.sum(d_route_d3[mx])/1000.
        rm['elevation_gain_m'] = np.sum(d_(route_altitude, N)[mx])/(N-1)
        
        
    if False:
        plt.figure()
        plt.plot(
            np.cumsum(d_route_d3),
            route_altitude,
        )
        plt.plot(
            np.cumsum(d_route_d3),
            np.cumsum(d_(route_altitude, N))/(N-1),
        )
        plt.grid()
        
    
    
    



