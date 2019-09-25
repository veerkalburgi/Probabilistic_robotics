import matplotlib.pyplot as plt
import numpy as np
from numpy import cos, sin, arctan2
from numpy import matmul as mm
from numpy.linalg import inv as mat_inv
from scipy.io import loadmat
import pdb

def get_circle(center, radius, body_color, edge_color):
    return plt.Circle(center, radius=radius, color=body_color, ec=edge_color)

def get_pose(center, theta, radius):
    x_rotation = [center[0], center[0] + radius*np.cos(theta)]
    y_rotation = [center[1], center[1] + radius*np.sin(theta)]
    return x_rotation, y_rotation

def get_G_t(v, w, angle, dt):
    return np.array([
                    [1, 0, ( (-v/w)*cos(angle) ) + ( (v/w)*cos(angle + (w*dt)) ) ],
                    [0, 1, ( (-v/w)*sin(angle) ) + ( (v/w)*sin(angle + (w*dt)) ) ],
                    [0, 0, 1]
                    ])

def get_V_t(v, w, angle, dt):
    v_0_0 = ( -sin(angle) + sin(angle + (w*dt)) ) / w
    v_0_1 = ( (v * (sin(angle) - sin(angle + (w*dt)))) / (w*w) ) + \
        ( (v * cos(angle + (w*dt)) * dt) / w )
    v_1_0 = ( cos(angle) - cos(angle + (w*dt)) ) / w
    v_1_1 = ( -(v * (cos(angle) - cos(angle + (w*dt)))) / (w*w) ) + \
        ( (v * sin(angle + (w*dt)) * dt) / w )
    return np.array([
                    [v_0_0, v_0_1],
                    [v_1_0, v_1_1],
                    [0, dt]
                    ])

def get_M_t(a_1, a_2, a_3, a_4, v, w):
    return np.array([
                    [( (a_1 * v*v) + (a_2 * w*w) ), 0],
                    [0, ( (a_3 * v*v) + (a_4 * w*w) )]
                    ])

def make_noise(cov_matrix):
    # assume distribution is zero-centered
    noisy_transition = \
        np.random.multivariate_normal(np.zeros(cov_matrix.shape[0]), cov_matrix)
    return np.reshape(noisy_transition, (-1,1))

def get_vel_input(curr_time):
    return 1 + (.5 * cos(2*np.pi * .2 * curr_time))

def get_omega_input(curr_time):
    return -.2 + (2 * cos(2*np.pi * .6 * curr_time))

def get_mu_bar(prev_mu, v, w, angle, dt):
    ratio = v/w
    m = np.array([
                    [(-ratio * sin(angle)) + (ratio * sin(angle + (w*dt)))],
                    [(ratio * cos(angle)) - (ratio * cos(angle + (w*dt)))],
                    [w*dt]
                ])
    return prev_mu + m

if __name__ == "__main__":
    dt = .1
    t = np.arange(0, 20+dt, dt)
    t = np.reshape(t, (1,-1))

    # belief (estimates from EKF)
    mu_x = np.zeros(t.shape)
    mu_y = np.zeros(t.shape)
    mu_theta = np.zeros(t.shape)   # radians

    # control inputs
    velocity = np.zeros(t.shape)
    omega = np.zeros(t.shape)

    ########################################################################################
    ############################## DEFINE PARAMETERS HERE ##################################
    ########################################################################################
    use_mat_data = True
    # noise in the command velocities (translational and rotational)
    alpha_1 = .1
    alpha_2 = .01
    alpha_3 = .01
    alpha_4 = .1
    # std deviation of range and bearing sensor noise for each landmark
    std_dev_range = .1
    std_dev_bearing = .05
    # starting belief - initial condition (robot pose)
    mu_x[0 , 0] = -5 + .5
    mu_y[0 , 0] = -3 - .7
    mu_theta[0 , 0] = (np.pi / 2) - .05
    # initial uncertainty in the belief
    sigma = np.array([
                        [1, 0, 0],  # x
                        [0, 1, 0],  # y
                        [0, 0, .1]  # theta
                    ])
    ########################################################################################
    ########################################################################################

    # landmarks (x and y coordinates)
    lm_x = [6, -7, 6]
    lm_y = [4, 8, -4]
    assert(len(lm_x) == len(lm_y))
    num_landmarks = len(lm_x)

    # ground truth
    x_pos_true = np.zeros(t.shape)
    y_pos_true = np.zeros(t.shape)
    theta_true = np.zeros(t.shape)  # radians

    # uncertainty due to measurement noise
    Q_t = np.array([
                    [(std_dev_range * std_dev_range), 0],
                    [0, (std_dev_bearing * std_dev_bearing)]
                    ])

    # set ground truth data
    if use_mat_data:
        # ground truth comes from file

        # all loaded vars are numpy arrays
        # all have shape of (1, 201)
        x = loadmat('hw2_soln_data.mat')
        
        # time
        t = x['t']
        # control inputs
        omega = x['om']
        velocity = x['v']
        # true states
        x_pos_true = x['x']
        y_pos_true = x['y']
        theta_true = x['th']
    else:
        # make new ground truth data

        # robot has initial condition of position (-5,-3) and 90 degree orientation
        x_pos_true[0 , 0] = -5
        y_pos_true[0 , 0] = -3
        theta_true[0 , 0] = np.pi / 2

        # TODO create my own ground truth data here
        for timestep in range(1, t.size):
            pass

    mu = np.array([mu_x[0,0], mu_y[0,0], mu_theta[0,0]])
    mu = np.reshape(mu, (-1, 1))

    # needed for plotting covariance bounds vs values
    bound_x = [np.sqrt(sigma[0 , 0]) * 2]
    bound_y = [np.sqrt(sigma[1 , 1]) * 2]
    bound_theta = [np.sqrt(sigma[2 , 2]) * 2]

    # run EKF
    for i in range(1,t.size):
        curr_v = velocity[0,i]
        curr_w = omega[0,i]
        prev_theta = mu_theta[0,i-1]

        G_t = get_G_t(curr_v, curr_w, prev_theta, dt)
        V_t = get_V_t(curr_v, curr_w, prev_theta, dt) 
        M_t = get_M_t(alpha_1, alpha_2, alpha_3, alpha_4, curr_v, curr_w)
        
        # prediction
        mu_bar = get_mu_bar(mu, curr_v, curr_w, prev_theta, dt)
        sigma_bar = mm(G_t, mm(sigma, np.transpose(G_t))) + \
            mm(V_t, mm(M_t, np.transpose(V_t)))

        # correction (updating belief based on landmark readings)
        real_x = x_pos_true[0 , i]
        real_y = y_pos_true[0 , i]
        real_theta = theta_true[0 , i]
        for j in range(num_landmarks):
            m_j_x = lm_x[j]
            m_j_y = lm_y[j]
            bel_x = mu_bar[0 , 0]
            bel_y = mu_bar[1 , 0]
            bel_theta = mu_bar[2 , 0]

            # get the sensor measurement
            q_true = ((m_j_x - real_x) ** 2) + ((m_j_y - real_y) ** 2)
            z_true = np.array([
                            [np.sqrt(q_true)],
                            [arctan2(m_j_y - real_y, m_j_x - real_x) - real_theta]
                            ])
            z_true += make_noise(Q_t)

            # figure out kalman gain for the given landmark and then update belief
            q = ((m_j_x - bel_x) ** 2) + ((m_j_y - bel_y) ** 2)
            z_hat = np.array([
                            [np.sqrt(q)],
                            [arctan2(m_j_y - bel_y, m_j_x - bel_x) - bel_theta]
                            ])
            H_t = np.array([
                            [-(m_j_x - bel_x) / np.sqrt(q), -(m_j_y - bel_y) / np.sqrt(q), 0],
                            [(m_j_y - bel_y) / q, -(m_j_x - bel_x) / q, -1]
                            ])
            S_t = mm(H_t, mm(sigma_bar, np.transpose(H_t))) + Q_t
            K_t = mm(sigma_bar, mm(np.transpose(H_t), mat_inv(S_t)))
            mu_bar = mu_bar + mm(K_t, z_true - z_hat)
            sigma_bar = mm((np.identity(sigma_bar.shape[0]) - mm(K_t, H_t)), sigma_bar)

        # update belief
        mu = mu_bar
        sigma = sigma_bar
        mu_x[0 , i] = mu[0 , 0]
        mu_y[0 , i] = mu[1 , 0]
        mu_theta[0 , i] = mu[2 , 0]

        # save covariances for plot later
        bound_x.append(np.sqrt(sigma[0 , 0]) * 2)
        bound_y.append(np.sqrt(sigma[1 , 1]) * 2)
        bound_theta.append(np.sqrt(sigma[2 , 2]) * 2)

    # make everything a list (easier for plotting)
    x_pos_true = x_pos_true.tolist()[0]
    y_pos_true = y_pos_true.tolist()[0]
    theta_true = theta_true.tolist()[0]
    mu_x = mu_x.tolist()[0]
    mu_y = mu_y.tolist()[0]
    mu_theta = mu_theta.tolist()[0]
    t = t.tolist()[0]

    ###############################################################################
    ###############################################################################
    # animate and plot
    radius = .5
    yellow = (1,1,0)
    black = 'k'

    world_bounds_x = [-10,10]
    world_bounds_y = [-10,10]
    
    p1 = plt.figure(1)
    for i in range(len(x_pos_true)):
        theta = theta_true[i]
        center = (x_pos_true[i],y_pos_true[i])

        # clear the figure before plotting the next phase
        plt.clf()
        
        # get the robot pose
        body = get_circle(center, radius, yellow, black)
        orientation_x, orientation_y = \
            get_pose(center, theta, radius)
        # plot the robot pose
        plt.plot(orientation_x, orientation_y, color=black)
        axes = plt.gca()
        axes.add_patch(body)

        # plot the markers
        plt.plot(lm_x, lm_y, '+', color=black)

        # animate (keep axis limits constant and make the figure a square)
        axes.set_xlim(world_bounds_x)
        axes.set_ylim(world_bounds_y)
        axes.set_aspect('equal')
        plt.pause(.025)

    # animation is done, now plot the estimated path
    step = 2
    plt.plot(mu_x[::step], mu_y[::step], '.', color='r', label="predicted")
    plt.plot(x_pos_true[::step], y_pos_true[::step], '.', color='b', label="truth")
    plt.legend()
    p1.show()

    # plot the states over time
    p2 = plt.figure(2)
    plt.subplot(311)
    plt.plot(t, x_pos_true, label="true")
    plt.plot(t, mu_x, label="predicted")
    plt.ylabel("x position (m)")
    plt.legend()
    plt.subplot(312)
    plt.plot(t, y_pos_true)
    plt.plot(t, mu_y)
    plt.ylabel("y position (m)")
    plt.subplot(313)
    plt.plot(t, theta_true)
    plt.plot(t, mu_theta)
    plt.ylabel("heading (rad)")
    plt.xlabel("time (s)")
    p2.show()

    # plot the states over time
    p3 = plt.figure(3)
    plt.subplot(311)
    plt.plot(t, np.array(x_pos_true) - np.array(mu_x), color='b', label="error")
    plt.plot(t, bound_x, color='r', label="uncertainty")
    plt.plot(t, [x * -1 for x in bound_x], color='r')
    plt.ylabel("x position (m)")
    plt.legend()
    plt.subplot(312)
    plt.plot(t, np.array(y_pos_true) - np.array(mu_y), color='b')
    plt.plot(t, bound_y, color='r')
    plt.plot(t, [x * -1 for x in bound_y], color='r')
    plt.ylabel("y position (m)")
    plt.subplot(313)
    plt.plot(t, np.array(theta_true) - np.array(mu_theta), color='b')
    plt.plot(t, bound_theta, color='r')
    plt.plot(t, [x * -1 for x in bound_theta], color='r')
    plt.ylabel("heading (rad)")
    plt.xlabel("time (s)")
    p3.show()

    # keep the plots open until user enters Ctrl+D to terminal (EOF)
    try:
        input()
    except EOFError:
        pass
    ###############################################################################
    ###############################################################################