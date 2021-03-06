'''
Create a simulation environment for a N-pendulum.
Example of use:

env = Pendulum(N)
env.reset()

for i in range(1000):
   env.step(zero(env.nu))
   env.render()

'''

import numpy as np
import pinocchio as pin
from .display import Display
from numpy.linalg import inv
import time
import os
import subprocess


class Visual:
    '''
    Class representing one 3D mesh of the robot, to be attached to a joint.
    The class contains:
    * the name of the 3D objects inside Gepetto viewer.
    * the ID of the joint in the kinematic tree to which the body is attached.
    * the placement of the body with respect to the joint frame.
    This class is only used in the list Robot.visuals (see below).
    '''

    def __init__(self, name, jointParent, placement):
        self.name = name                  # Name in gepetto viewer
        self.jointParent = jointParent    # ID (int) of the joint
        self.placement = placement        # placement of the body wrt joint, i.e. bodyMjoint

    def place(self, display, oMjoint):
        oMbody = oMjoint*self.placement
        display.place(self.name, oMbody, False)


class Pendulum:
    '''
    Define a class Pendulum with nbJoint joints.
    The members of the class are:
    * viewer: a display encapsulating a gepetto viewer client to create 3D
              objects and place them.
    * model: the kinematic tree of the robot.
    * data: the temporary variables to be used by the kinematic algorithms.
    * visuals: the list of all the 'visual' 3D objects to render the robot,
               each element of the list being
    an object Visual (see above).
    '''

    def __init__(self, nbJoint=1, noise_stddev=0.0):
        '''Create a Pinocchio model of a N-pendulum, with N the argument <nbJoint>.'''
        self.viewer = Display()
        self.visuals = []
        self.model = pin.Model()
        self.createPendulum(nbJoint)
        self.data = self.model.createData()
        self.noise_stddev = noise_stddev

        self.q0 = np.zeros(self.model.nq)

        self.DT = 5e-2   # Time step length
        self.NDT = 1      # Number of Euler steps per integration (internal)
        self.Kf = .10    # Friction coefficient
        self.vmax = 8.0    # Max velocity (clipped if larger)
        self.umax = 2.0    # Max torque   (clipped if larger)
        # If true, state is [cos(q),sin(q),qdot], else [q,qdot]
        self.withSinCos = False

    def record_pendulum(self, custom_namefile='', frame_dir=os.getcwd()):
        print('Start robot recording')
        windowID = self.viewer.viewer.gui.getWindowList()[0]
        nameFile = frame_dir + os.sep + custom_namefile + \
            '_pendulum_%d_joints' % (self.model.njoints - 1)
        if not os.path.isdir(frame_dir):
            os.makedirs(frame_dir, 0o777)
            print('Created folder {}'.format(frame_dir))
        self.viewer.viewer.gui.startCapture(windowID, nameFile, 'png')

    def end_record(self, nameFile, frame_dir):
        nameFile += '_pendulum_{}_joints'.format(self.model.njoints - 1)
        windowID = self.viewer.viewer.gui.getWindowList()[0]
        self.viewer.viewer.gui.stopCapture(windowID)
        print('Ended robot recording')

        # Generate videos  # Buggy
        # dest_file = frame_dir + os.sep + nameFile
        # subprocess.run(['convert', '{}*'.format(dest_file),
        #                 '{}.mp4'.format(dest_file)])
        # Clean up images
        # for el in os.listdir(movie_dir):
        #     if '.png' in el:
        #         subprocess.run(['rm', '{}/{}'.format(movie_dir, el)])

        # Clean temporary folder of imageMagick
        # subprocess.run(['rm', '-rf', '/tmp/magick-*'])

    def createPendulum(self, nbJoint, rootId=0, prefix='',
                       jointPlacement=None):
        color = [red, green, blue, transparency] = [1, 1, 0.78, 1.0]
        colorred = [1.0, 0.0, 0.0, 1.0]

        jointId = rootId
        jointPlacement = jointPlacement if jointPlacement != None else pin.SE3.Identity()
        length = 1.0
        mass = length
        inertia = pin.Inertia(mass,
                              np.array([0.0, 0.0, length/2]).T,
                              mass/5*np.diagflat([1e-2, length**2,  1e-2]))

        for i in range(nbJoint):
            istr = str(i)
            name = prefix+"joint"+istr
            jointName = name+"_joint"
            jointId = self.model.addJoint(
                jointId, pin.JointModelRY(), jointPlacement, jointName)
            self.model.appendBodyToJoint(jointId, inertia, pin.SE3.Identity())
            try:
                self.viewer.viewer.gui.addSphere(
                    'world/'+prefix+'sphere'+istr, 0.15, colorred)
            except:
                pass
            self.visuals.append(
                Visual('world/'+prefix+'sphere'+istr, jointId, pin.SE3.Identity()))
            try:
                self.viewer.viewer.gui.addCapsule(
                    'world/'+prefix+'arm'+istr, .1, .8*length, color)
            except:
                pass
            self.visuals.append(Visual('world/'+prefix+'arm'+istr, jointId,
                                       pin.SE3(np.eye(3), np.array([0., 0., length/2]))))
            jointPlacement = pin.SE3(np.eye(3), np.array([0.0, 0.0, length]).T)

        self.model.addFrame(pin.Frame('tip', jointId, 0,
                            jointPlacement, pin.FrameType.OP_FRAME))

    def display(self, q):
        ''' Display the robot in the viewer '''
        pin.forwardKinematics(self.model, self.data, q)
        for visual in self.visuals:
            visual.place(self.viewer, self.data.oMi[visual.jointParent])
        self.viewer.viewer.gui.refresh()

    ''' Size of the q vector '''
    @property
    def nq(self): return self.model.nq
    ''' Size of the v vector '''
    @property
    def nv(self): return self.model.nv
    ''' Size of the x vector '''
    @property
    def nx(self): return self.nq+self.nv
#    @property
#    def nobs(self): return self.nx+self.withSinCos
    ''' Size of the u vector '''
    @property
    def nu(self): return self.nv

    def reset(self, x0=None):
        ''' Reset the state of the environment to x0 '''
        if x0 is None:
            # for i in range(self.model.njoints):
            q0 = np.pi*(np.random.rand(self.nq)*2-1)
            v0 = np.random.rand(self.nv)*2-1
            x0 = np.hstack([q0, v0])
        assert len(x0) == self.nx
        self.x = x0.copy()
        self.r = 0.0
        return self.obs(self.x)

    def step(self, u):
        ''' Simulate one time step '''
        u = u if type(u) is np.ndarray else [u]
        assert(len(u) == self.nu)
        _, self.r = self.dynamics(self.x, u)
        return self.obs(self.x), self.r

    def obs(self, x):
        ''' Compute the observation of the state '''
        if self.withSinCos:
            return np.vstack([np.vstack([np.cos(qi), np.sin(qi)]) for qi in x[:self.nq]]
                             + [x[self.nq:]],)
        else:
            return x.copy()

    def tip(self, q):
        '''Return the altitude of pendulum tip'''
        pin.framesKinematics(self.model, self.data, q)
        return self.data.oMf[1].translation[2, 0]

    def dynamics(self, x, u, display=False):
        '''
        Dynamic function: x,u -> xnext=f(x,y).
        Put the result in x (the initial value is destroyed).
        Also compute the cost of taking this step.
        Return x for convenience along with the cost.
        '''

        def modulePi(th): return (th+np.pi) % (2*np.pi)-np.pi
        def sumsq(x): return np.sum(np.square(x))

        cost = 0.0
        q = modulePi(x[:self.nq])
        v = x[self.nq:]
        u = np.clip(np.reshape(np.array(u), self.nu), -self.umax, self.umax)

        DT = self.DT/self.NDT
        for i in range(self.NDT):
            pin.computeAllTerms(self.model, self.data, q, v)
            M = self.data.M
            b = self.data.nle * 0.1
            inv_M = inv(M)
            z = (u-self.Kf*v-b)
            a = inv_M.dot(z)
            a = a.reshape(self.nv) + np.random.randn(self.nv)*self.noise_stddev
            self.a = a

            q += (v+0.5*DT*a)*DT
            v += a*DT
            cost += (sumsq(q) + 1e-1*sumsq(v) + 1e-3 *
                     sumsq(u))*DT  # cost function

            if display:
                self.display(q)
                time.sleep(1e-4)

        x[:self.nq] = modulePi(q)
        x[self.nq:] = np.clip(v, -self.vmax, self.vmax)

        return x, cost

    def render(self):
        q = self.x[:self.nq]
        self.display(q)
        time.sleep(self.DT/10)
