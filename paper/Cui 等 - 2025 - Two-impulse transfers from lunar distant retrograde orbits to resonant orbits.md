# Two-Impulse Transfers from Lunar Distant Retrograde Orbits to Resonant Orbits

Shuhao Cui* and Yue Wang†

Beihang University, 102206 Beijing, People's Republic of China

Ruikang Zhang

Chinese Academy of Space Technology, 100094 Beijing, China

and

Hao Zhang $^{\S}$ and Yang Gao $^{\dagger}$

Chinese Academy of Sciences, 100094 Beijing, China

https://doi.org/10.2514/1.G008582

As unique types of orbits in the cislunar space, distant retrograde orbits (DROs) and resonant orbits (ROs) are of great significance in future cislunar explorations, and the transfer between them deserves special attention. The design of transfer trajectories between these two kinds of orbits remains a challenge due to their stability. In this study, a novel transfer pathway from DROs and ROs is constructed based on a search and optimization methodology, which could offer an alternative for mission design related to these two orbits. Two-impulse transfers for both planar and nonplanar cases are designed in the circular restricted three-body problem, and three types of transfer orbits are obtained and characterized, including the direct transfer, the lunar gravity assisted transfer, and the external transfer. Planar transfers are also refined in the bicircular restricted four-body problem in consideration of the solar gravity. Furthermore, representative transfer orbits are transitioned into the ephemeris model to validate the preliminary design, and the result indicates that the transfer cost fluctuates with different departure epochs for all types of transfers.

# Nomenclature

C = Jacobi constant   
$G$ = gravitational constant, $\mathrm{m}^3 /(\mathrm{kg}\cdot \mathrm{s}^2)$   
$J(y)$ objective function in the optimization phase   
$m_{s}$ = mass of the sun, nondimensional unit   
$m_{1},m_{2}$ mass of the Earth and the moon, kg   
$r_e, r_m$ = radius of the Earth and the moon, nondimensional units   
$r_1, r_2, r_3 = \text{distance between the spacecraft and each of the primaries, nondimensional units}$   
$T$ = transfer time, nondimensional unit   
$t_{\mathrm{ins}}$ time from the apogee to the insertion point on the final orbit, nondimensional unit   
$X$ state vector in the synodic frame, nondimensional unit   
$x_{\mathrm{dep}},x_{\mathrm{ins}}$ state of the departure point in the initial orbit and the insertion point in the final orbit, nondimensional units   
$x_{i},x_{f}$ = initial and final states of the transfer orbit, non-dimensional units   
y optimization variables in the optimization phase   
$\alpha$ ratio of the velocity in the tangential direction of the departure point   
$\beta$ ratio of the velocity in the normal direction of the departure point

$\Delta v_{1}, \Delta v_{2} =$ departure and insertion impulses, nondimensional units   
$\theta_{s0}$ = initial solar phase, rad   
$\mu$ mass ratio of the Earth-moon system   
$\rho$ distance from the barycenter of the Earth-moon system to the sun, nondimensional unit   
$\Omega_3, \Omega_4 =$ effective potential in the circular restricted three-body problem and bicircular restricted four-body problem   
$\omega_{s}$ = angular velocity of the sun, nondimensional unit

# I. Introduction

WITH the lunar missions progressing steadily, such as NASA's Artemis program [1] and China's Chang'e Project [2], the interest in further exploration of cislunar space has been revived. To make full use of cislunar space and conduct crewed operations in the future, various techniques need to be handled, not only a quick round trip between the Earth and the moon but also transfers between various periodic orbits in the Earth-moon system.

Recently, two types of periodic orbits, the distant retrograde orbits (DROs) and the resonant orbits (ROs), have gradually attracted researchers' attention due to their specific characteristics and promising applications. DROs, as a family of stable periodic orbits moving retrogradely around the moon in the synodic frame, have been discovered since the 1960s [3,4] and considered as a good option for long-term residence [5,6]. In the Asteroid Redirect Mission [7,8], a near-Earth asteroid (NEA) would have been captured and placed into the DRO, where the NEA could be maintained over 100 years without correction maneuvers, and astronauts could explore the material of the asteroid and return samples to the Earth. As another specific type of periodic orbit, ROs also possess desirable properties, widely employed in mission design. ROs with several resonance ratios are stable, which could facilitate prolonged scientific observation, such as the Interstellar Boundary Explorer (IBEX) [9] and the Transiting Exoplanet Survey Satellite (TESS) [10], located in the 3:1 and 2:1 ROs in cislunar space, respectively. Diverse geometric shapes and the wide accessible range of resonance orbits [11,12] enable their usage in space domain awareness [13-15] and space environment detection [16], simultaneously covering hot spots such as the geosynchronous orbit region, the lunar vicinity, and the libration points.

Besides the orbital characteristics and their potential applications, the transfers associated with these orbits also attract much attention of researchers. Different transfer problems have been investigated between DROs and other periodic orbits, including low Earth orbits (LEOs) [17-20], low lunar orbits [21,22], near rectilinear halo orbits (NRHOs) [23-26], and so on. Capdevila and Howell [27] proposed a transfer network centering on DROs by the multiple shooting method and the pseudoarclength continuation scheme, connecting the regions of the Earth, moon, and triangular libration points. Furthermore, because DROs possess a much higher orbital energy than the two-body orbits around Earth, the trajectories from DROs to low Mars orbits (LMOs) have been proved to require less transfer costs than the trajectory from LEOs to LMOs [28]. As for ROs, several transfer pathways have been constructed. For instance, Vaquero and Howell [29] identified homoclinic- and heteroclinic-type trajectories between unstable ROs without extra transfer cost by leveraging the invariant manifold structures. Vaquero and Howell [30] also constructed the transfers from the LEO to the Earth-moon libration points via resonant arcs. Bonasera and Bosanac [31] used a manifold learning technique to solve the high dimensionality of Poincaré maps in the transitions between tori near resonances, enabling rapid identification of initial guesses. Additionally, the investigation of the transfer problems related to ROs have been extended to other three-body systems, like the Mars system [32], the Jovian system [33,34], and the Saturnian system [35].

As evidenced by the literature, the transfers associated with DROs or ROs have been widely explored. However, little attention has been paid to building the transfer pathway between DROs and stable ROs. From a methodological perspective, the stability of periodic orbits poses a significant challenge for the transfer design, as the widely used unstable manifold structure no longer exists [36]. Moreover, the transfer between these orbits acts as a crucial component in the future cislunar space transfer network. This transfer could be incorporated into an extended, RO mission from a spacecraft initially on a DRO, enriching the objectives of one cislunar mission. It also could be employed to service a spacecraft on a RO from a DRO space port and enhance the in-orbit servicing capacity of DROs.

This investigation focuses on building the novel transfer pathway from DROs to ROs that could integrate solar and lunar gravity in realistic dynamical models, which may have practical implications for future cislunar infrastructure. The main contributions can be summarized as follows:

1) A novel transfer pathway from DROs to ROs is established in the cislunar space, which fills a gap in research on the transfer problems with these two kinds of orbits. Because of the unavailability of unstable manifold structure, a two-step method is adopted to design the two-impulse transfer, including the search phase and the optimization phase. The method is capable of revealing the global transfer solutions and has good applicability for both planar and nonplanar transfers, especially suitable for the transfer between stable orbits.

2) The transfer problem is solved not only in ideal models, like the circular restricted three-body problem (CR3BP) and the bicircular restricted four-body problem (BR4BP) but also in the high-fidelity ephemeris model for practical reasons. In the ideal models, the global solutions are displayed, and typical transfer orbits are classified and analyzed. Then, representative transfer orbits are transitioned into the ephemeris model further to validate the effectiveness of the preliminary design.

The paper is structured as follows. Dynamical models and baseline DROs and ROs are introduced in Sec. II. Then, Sec. III presents the optimization method of the two-impulse transfer design, consisted of the search phase and the optimization phase. In Secs. IV-VI, the transfer pathways between DROs and ROs in different dynamical models are constructed and analyzed. The paper is finally concluded in Sec. VII.

# II. Background

This investigation employs three dynamical models for the computation and analysis of the transfer trajectories. The first model is the

CR3BP [17,27,37], which is leveraged to calculate the initial and final baseline orbits and design the transfer preliminarily. Then, the BR4BP [38-40], considering the gravitational influence of the sun, is adopted for the refinement of the transfer orbits. Finally, the ephemeris model [11,41,42] is established, enabling the transition and validation of the transfer orbits in real scenarios.

# A. Circular Restricted Three-Body Problem

The CR3BP is a classical model to describe the orbital motion of a spacecraft in the Earth-moon system. Both the Earth and the moon are considered as point masses moving around their barycenter in circular orbits. The motion of the massless spacecraft is usually formulated in a synodic frame, with the origin located at the barycenter of the two primaries, the $x$ axis pointing from the origin to the moon, the $z$ axis paralleling to the angular momentum of the system, and the $y$ axis satisfying the right-handed rule, as shown in Fig. 1a. The masses of the Earth and the moon are denoted by $m_{1}$ and $m_{2}$ , respectively; then the mass ratio, an important parameter of the system, is expressed as $\mu = m_{2} / (m_{1} + m_{2})$ . The state vector $\bar{X} = [x y z \dot{x} \dot{y} \dot{z}]^{T}$ , which represents the position and velocity of the spacecraft in the synodic frame, follows the nondimensional equations of motion,

$$
\ddot {x} - 2 \dot {y} = \frac {\partial \Omega_ {3}}{\partial x}, \quad \ddot {y} + 2 \dot {x} = \frac {\partial \Omega_ {3}}{\partial y}, \quad \ddot {z} = \frac {\partial \Omega_ {3}}{\partial z} \tag {1}
$$

where $\Omega_3$ is the effective potential,

$$
\Omega_ {3} = \frac {1}{2} \left(x ^ {2} + y ^ {2}\right) + \frac {1 - \mu}{r _ {1}} + \frac {\mu}{r _ {2}} + \frac {1}{2} \mu (1 - \mu) \tag {2}
$$

with $r_1$ and $r_2$ indicating the distance between the spacecraft and the primaries:

$$
r _ {1} = [ (x + \mu) ^ {2} + y ^ {2} + z ^ {2} ] ^ {1 / 2}, r _ {2} = [ (x - 1 + \mu) ^ {2} + y ^ {2} + z ^ {2} ] ^ {1 / 2} \tag {3}
$$

Because only the gravity is considered and other perturbations are ignored, the CR3BP is autonomous and has an energy integral of the motion known as the Jacobi constant:

$$
C = 2 \Omega_ {3} - \left(\dot {x} ^ {2} + \dot {y} ^ {2} + \dot {z} ^ {2}\right) \tag {4}
$$

# B. Bicircular Restricted Four-Body Problem

Based on the CR3BP, the impact of solar gravity is further considered in the BR4BP. The sun, with mass $m_{s}$ , is assumed to move in a coplanar and circular orbit around the barycenter of the Earth-moon system at the angular velocity of $\omega_{s}$ , while the distance between the barycenter of the Earth-moon system and the sun is denoted as $\rho$ , as shown in Fig. 1b. The motion of the spacecraft is described in the sun-Earth-moon system with some modification relative to Eq. (1), which is expressed as

$$
\ddot {x} - 2 \dot {y} = \frac {\partial \Omega_ {4}}{\partial x}, \quad \ddot {y} + 2 \dot {x} = \frac {\partial \Omega_ {4}}{\partial y}, \quad \ddot {z} = \frac {\partial \Omega_ {4}}{\partial z} \tag {5}
$$

where $\Omega_4$ is the effective potential in the BR4BP,

$$
\Omega_ {4} = \Omega_ {3} + \frac {m _ {s}}{r _ {3} (t)} - \frac {m _ {s}}{\rho^ {2}} \left(x \cos \left(\omega_ {s} t\right) + y \sin \left(\omega_ {s} t\right)\right) \tag {6}
$$

with $r_3$ indicating the distance between the spacecraft and the sun:

$$
r _ {3} (t) = \left[ (x - \rho \cos (\omega_ {s} t)) ^ {2} + (y - \rho \sin (\omega_ {s} t)) ^ {2} + z ^ {2} \right] ^ {1 / 2} \tag {7}
$$

Because of the motion of the sun, the effective potential becomes time dependent in the BR4BP, and the energy integral is no longer a

![](images/8199a6067b98eb66454f482d96e9bc789c8b36c229cfccf21eadd49feedd3cf8.jpg)  
a) CR3BP

![](images/dfb607bb2d1ae54cab708c3048d7cb4bbca32c7ea01d5d358190a19936b178f0.jpg)  
b) BR4BP

![](images/6a245f2bf4c0d811d9306a16f5e5f8089cd7f060d7d1c69793226c421376fa92.jpg)  
c) Ephemeris model   
Fig. 1 Orbital dynamical models in the Earth-moon system.

Table 1 Physical parameters used in the dynamical model   

<table><tr><td>Symbol</td><td>Value</td><td>Meaning</td></tr><tr><td>μ</td><td>1.21506683 × 10-2</td><td>Mass ratio of the Earth–moon system</td></tr><tr><td>ms</td><td>3.28900541 × 105</td><td>Nondimensional mass of the sun</td></tr><tr><td>ωs</td><td>9.25195985 × 10-1</td><td>Nondimensional angular velocity of the sun</td></tr><tr><td>ρ</td><td>3.88811143 × 102</td><td>Nondimensional sun–(Earth–moon) distance</td></tr><tr><td>DU, km</td><td>3.84405000 × 105</td><td>Distance unit</td></tr><tr><td>TU, days</td><td>4.34811305</td><td>Time unit</td></tr><tr><td>VU, m/s</td><td>1023.23281</td><td>Velocity unit</td></tr></table>

constant. The physical parameters of the sun-Earth-moon system and the nondimensional units are all listed in Table 1.

# C. Ephemeris Model

To better align with real mission scenarios, the ephemeris model is established according to the restricted $N$ -body problem (RNBP), by considering the planetary ephemerides. The Earth is selected as the central body, while the relative position of the moon and sun with respect to the Earth is instantaneously obtained by the DE438 file. The whole equation of the motion of the spacecraft in the Earth-centered J2000 inertial frame is written as

$$
\ddot {r} _ {q i} = - \frac {G \left(m _ {i} + m _ {q}\right)}{r _ {q i} ^ {3}} r _ {q i} + G \sum_ {\substack {j = 1 \\ j \neq i, q}} ^ {n} m _ {j} \left(\frac {r _ {i j}}{r _ {i j} ^ {3}} - \frac {r _ {q j}}{r _ {q j} ^ {3}}\right) \tag{8}
$$

where $G$ denotes the gravitational constant and the subscripts $i, q$ , and $j$ refer to the spacecraft, the central body, and the perturbing bodies, respectively, as shown in Fig. 1c.

# D. DROs and ROs in CR3BP

Two intriguing types of periodic orbits in the CR3BP, DROs and ROs, are selected as baseline orbits in the subsequent transfer design. The family of DROs moves retrogradely around the moon in the synodic frame and is identified as the family C by Broucke [3]. By natural parameter continuation, the entire DRO family can be obtained, as shown in Fig. 2a, and it is apparent that the perigee, also the intersection with the horizontal axis, asymptotically approaches the Earth inward and the moon outward. Each orbit is colored by its Jacobi constant. The variations of the orbit period and the stability index with respect to the Jacobi constant are plotted in Fig. 2b. Evidently, the orbital period decreases monotonically as the Jacobi constant increases, that is, as the orbital energy decreases. Additionally, the stability indices of the entire family are either equal to 1 or close to 1, indicating that the DRO family exhibits favorable stability.

![](images/d75729d96c23bb2a81ff829e2281b17dea55dcadf176424ceb4f4440a675d2e6.jpg)  
a) DRO family

![](images/0ed95b2eb82f445f3bd613ac6e4b0fb091680f64c9e741329f8cb4ff6c0db277.jpg)  
b) Orbital period, stability index and Jacobi constant   
Fig. 2 The DRO family and the variation of orbital parameters.

Table 2 Orbital characteristics of the selected DROs and ROs $(y = \dot{x} = 0)$   

<table><tr><td>Orbit</td><td>x, nd</td><td>z, nd</td><td>y, nd</td><td>z, nd</td><td>T, days</td><td>C</td><td>Az, nd</td></tr><tr><td>2:1 DRO</td><td>1.1754</td><td>0</td><td>-0.4943</td><td>0</td><td>13.66</td><td>2.9305</td><td>0</td></tr><tr><td>3:1 DRO</td><td>1.1202</td><td>0</td><td>-0.4618</td><td>0</td><td>9.11</td><td>2.9700</td><td>0</td></tr><tr><td>3:2 RO</td><td>-1.1453</td><td>0</td><td>0.4633</td><td>0</td><td>54.64</td><td>2.8520</td><td>0</td></tr><tr><td>3:2 RRO</td><td>-1.0878</td><td>0.2000</td><td>0.3581</td><td>0</td><td>54.40</td><td>2.8725</td><td>0.2</td></tr><tr><td>3:2 ARO</td><td>-1.1318</td><td>0</td><td>0.4626</td><td>0.1999</td><td>54.57</td><td>2.8031</td><td>0.2</td></tr><tr><td>3:1 RO</td><td>-0.8805</td><td>0</td><td>0.3921</td><td>0</td><td>27.32</td><td>2.9098</td><td>0</td></tr><tr><td>3:1 RRO</td><td>-0.7660</td><td>0.2000</td><td>0.0601</td><td>0</td><td>27.22</td><td>3.1302</td><td>0.2</td></tr><tr><td>3:1 ARO</td><td>-0.8357</td><td>0</td><td>0.3450</td><td>0.3473</td><td>27.31</td><td>2.8711</td><td>0.2</td></tr></table>

"nd", corresponding to the nondimensional equations in Secs. II.A and II.B.

Note that several orbits possess periods in integer ratios to the lunar sidereal period; for instance, the orbital period of the 2:1 DRO is half of the lunar sidereal period, and, similarly, the 3:1 DRO corresponds to 1/3. These two specific DROs, highlighted in bold black in Fig. 2a, will be chosen as the initial orbits for the following research, and their orbital characteristics are listed in Table 2, corresponding to the black dashed lines in Fig. 2b.

ROs have a period that is approximately in an integer ratio to the lunar sidereal period. Conventionally, in a $p: q$ resonance, the time it takes for $p$ revolutions around the Earth is roughly equal to the time that the moon completes $q$ revolutions. For the $p: q$ resonant orbital family, only the ratio of the precise $p: q$ RO is an integer, and the remaining orbits of the whole family can be generated by natural parameter continuation. Portions of the 3:2 and 3:1 RO families are depicted in Figs. 3a and 4a [43], in which the black bold trajectories represent the orbits with precise resonance ratios, selected as final orbits for planar transfers. Similar to DROs, the period of ROs decreases as the orbital energy decreases, and the orbits are stable or near stable, as shown in Figs. 3b and 4b.

According to the bifurcation theory [44], when a pair of eigenvalues of the monodromy matrix of periodic orbits collides on the real axis at $+1$ , a tangent bifurcation occurs, accompanied by the generation of three-dimensional (3D) orbits. Two types of 3D ROs are computed, as illustrated in Fig. 5. By employing the Mirror Theorem

[45], it can be observed that one type of orbit is symmetric about the $x - z$ plane, termed as a reflection resonant orbit (RRO), and is analogous to halo orbits in libration-point orbits (LPOs). Another type of orbit is symmetric about the $x$ axis, termed as an axial resonant orbit (ARO), and is analogous to axial orbits in LPOs [46]. To facilitate the study, the $z$ amplitude of the 3D RO is set as a characteristic parameter for a specific trajectory, denoted as $A z$ . The 3D ROs with Az equal to 0.2, highlighted in black bold in Fig. 5, are chosen as the final orbits for the nonplanar transfer, with the parameters listed in Table 2.

# III. Optimization Method for Two-Impulse Transfers

A two-impulse transfer is employed from the DRO to the RO, including departure and insertion impulses. Because of the stability of the initial and final orbits, it is infeasible to leverage the unstable manifold structure. Therefore, a two-step transfer design method, with the search phase and the optimization phase, is presented.

# A. Search Phase

The search phase involves selecting appropriate parameters as variables, gridding them within certain bounds, and integrating the trajectories for initial feasible solutions.

![](images/794f71914b309f4110e2ff8f78b1a95691370cc0682c325fa7dffef385467fc3.jpg)  
Fig. 3 The 3:2 RO family and the variation of orbital parameters.

![](images/0b87aa6afa708d2c479a0606be5746833fd0975eceecfc94e2ac12059afee95b.jpg)  
Fig. 4 The 3:1 RO family and the variation of orbital parameters.

![](images/f032a98b45af7472a609d7104a013f2d8a78b8cdb01cd011225d5aa4767eef70.jpg)

![](images/f20b86f30df75b282cbb78a04cf84910b000aa494ea9a8a816485f5939b2a01e.jpg)

![](images/574dbe463022e9f6468750de42cbd5c34cd93f35e1547bbe3a851af372c74235.jpg)

![](images/f2ed0e3204425b6b80c5eb5d05152e0185664899f6363d63eb1b2f527b541aa3.jpg)

![](images/c7fe825c9af56317490f9237b62c7fba71e296fcca53886e0d95fecb82f3fbd3.jpg)  
a) 3:2 RRO family   
b) 3:2 ARO family

![](images/82aacdd12864bd23b2a259fc1db823b7dc80ede867caf95308bcc46dcf1b377b.jpg)

![](images/34ade1cd56bb1ed7b484db03ec8b3cec6132ac810f0ee3e55f82a14a6822bbd8.jpg)

![](images/78ca6fd4fde2f357346c070b33ccbf0c989d1d12c72c41c30f4caa5e5e2397dc.jpg)  
c) 3:1 RRO family   
d) 3:1 ARO family   
Fig. 5 Two types of 3D RO families in 3:2 and 3:1 resonance ratio.

Table 3 The bounds and discretization of the search variables   

<table><tr><td>Variable</td><td>Minimum</td><td>Maximum</td><td>Number of points</td><td>Meaning</td></tr><tr><td>Departure point</td><td>—</td><td>—</td><td>200</td><td>Discrete points in equal time intervals on the initial orbit</td></tr><tr><td>α</td><td>0.5</td><td>2.5</td><td>1001</td><td>Ratio of the velocity in the tangential direction</td></tr><tr><td>β</td><td>-0.5</td><td>0.5</td><td>101</td><td>Ratio of the velocity in the normal direction</td></tr><tr><td>θs0</td><td>0</td><td>2π</td><td>18</td><td>Initial solar phase</td></tr></table>

The search variables should be capable of fully describing the entire transfer process. That is to say, once the search variables are given, the transfer orbit is uniquely determined. The first search variable is the position of the departure point on the initial orbit. Because the initial orbits are difficult to describe analytically, they are obtained by numerical integration and then split into discrete points in equal time intervals. The second search variable $\alpha$ is the ratio of the velocity after and before the departure impulse in the tangential direction. As for a nonplanar transfer, the third search variable $\beta$ is included, referring to the ratio of the velocity in the normal direction. Additionally, when the transfer is further designed in the BR4BP, the initial phase of the sun $\theta_{s0}$ needs to be considered as the fourth search variable, ranging from 0 to $2\pi$ . Table 3 summarizes the boundaries of search variables and the numbers of grid points.

Through the forward integration with groups of search variables, multiple transfer trajectories are obtained and then filtered. If the transfer trajectory intersects the final orbit or is locally minimal in distance with the final orbit, the values of the parameters and transfer time will be recorded as initial guesses of feasible solutions. It is possible that a transfer trajectory in a certain integral time has more than one intersection or minimum with the final orbit, resulting that one combination of the search variables with different transfer times could form different initial guesses.

# B. Optimization Phase

The optimization phase is to convert the impulse transfer problem to a nonlinear programming (NLP) problem, which determines the optimization variables to minimize the fuel consumption under constraints.

The departure point is assumed to be fixed in the optimization phase. Therefore, for the planar transfer in the CR3BP, the optimization variables are given by

$$
y = \left\{\alpha , T, t _ {\text {i n s}} \right\} \tag {9}
$$

where $T$ is the transfer time and $t_{\mathrm{ins}}$ is the time from a predefined initial point at the apogee to the insertion point on the final orbit, representing the position of the insertion point.

The optimization objective is to minimize the sum of the two impulses and can be written as the objective function

$$
J (y) = \Delta v _ {1} + \Delta v _ {2} \tag {10}
$$

where $\Delta v_{1}$ and $\Delta v_{2}$ represent the departure and insertion impulses,

$$
\Delta v _ {1} = \left(\left(\dot {x} _ {i} - \dot {x} _ {\mathrm {d e p}}\right) ^ {2} + \left(\dot {y} _ {i} - \dot {y} _ {\mathrm {d e p}}\right) ^ {2} + \left(\dot {z} _ {i} - \dot {z} _ {\mathrm {d e p}}\right) ^ {2}\right) ^ {1 / 2} \tag {11}
$$

$$
\Delta v _ {2} = \left(\left(\dot {x} _ {\text {i n s}} - \dot {x} _ {f}\right) ^ {2} + \left(\dot {y} _ {\text {i n s}} - \dot {y} _ {f}\right) ^ {2} + \left(\dot {z} _ {\text {i n s}} - \dot {z} _ {f}\right) ^ {2}\right) ^ {1 / 2} \tag {12}
$$

with $\pmb{x}_{\mathrm{dep}} = [x_{\mathrm{dep}},y_{\mathrm{dep}},z_{\mathrm{dep}},\dot{x}_{\mathrm{dep}},\dot{y}_{\mathrm{dep}},\dot{\dot{z}}_{\mathrm{dep}}]^T$ being the state of the departure point in the initial orbit, $\pmb{x}_{\mathrm{ins}} = [x_{\mathrm{ins}},y_{\mathrm{ins}},z_{\mathrm{ins}},\dot{x}_{\mathrm{ins}},\dot{y}_{\mathrm{ins}},$ $\dot{z}_{\mathrm{ins}}]^T$ being the state of the insertion point in the final orbit, $\pmb{x}_i = [x_i,y_i,z_i,\dot{x}_i,\dot{y}_i,\dot{z}_i]^T$ , and $\pmb{x}_f = [x_f,y_f,z_f,\dot{x}_f,\dot{y}_f,\dot{z}_f]^T$ being the initial and final states of the transfer trajectory.

The optimization problem satisfies the following constraints. First, the position of the insertion point needs to coincide with the final

point of the transfer trajectory, meeting the continuity condition. Then, the final velocity of the transfer trajectory needs to be parallel to the velocity of the insertion point in the final orbit in the planar case. In addition, the transfer orbit should not impact the Earth or the moon. These constraints can be expressed as

$$
\left(x _ {f} - x _ {\text {i n s}}\right) ^ {2} + \left(y _ {f} - y _ {\text {i n s}}\right) ^ {2} + \left(z _ {f} - z _ {\text {i n s}}\right) ^ {2} = 0 \tag {13}
$$

$$
\frac {\boldsymbol {v} _ {f} \boldsymbol {v} _ {\text {i n s}}}{\| \boldsymbol {v} _ {f} \| \| \boldsymbol {v} _ {\text {i n s}} \|} - 1 = 0 \tag {14}
$$

$$
r _ {e} ^ {2} - (x + \mu) ^ {2} - y ^ {2} - z ^ {2} <   0 \tag {15}
$$

$$
r _ {m} ^ {2} - (x + \mu - 1) ^ {2} - y ^ {2} - z ^ {2} <   0 \tag {16}
$$

where $r_e$ and $r_m$ are the mean radii of the Earth and the moon, respectively. During the optimization, the angle constraint of the velocity Eq. (14) can be relaxed from zero to a certain angle $\theta$ :

$$
\cos (\theta) - \frac {\boldsymbol {v} _ {f} \boldsymbol {v} _ {\text {i n s}}}{\| \boldsymbol {v} _ {f} \| \| \boldsymbol {v} _ {\text {i n s}} \|} <   0 \tag {17}
$$

Although the transition from equality to inequality adds some complexity to the constraint, it is helpful for expanding the solution plane and finding more feasible solutions. Moreover, the impact check can be separately verified after the optimization.

The NLP problem is solved by the sequential quadratic programming algorithm through the constrained optimization solver fmincon in MATLAB [47]. The tolerances of the objective function and constraints are set to be $10^{-10}$ . The transfer orbits in the optimization phase are integrated by the variable-step-size Runge-Kutta method of orders 7 and 8 with absolute and relative tolerances of $10^{-12}$ .

By involving new search variables and corresponding optimization variables, this two-step transfer design method demonstrates good scalability, allowing the transition from the planar transfer in the CR3BP into more complex scenarios. If the initial or final orbit is a 3D orbit, the normal component of the departure impulse could be included for a nonplanar transfer. Additionally, when the influence of the solar gravity is involved, the orbit could be integrated in the BR4BP with the initial solar phase taken into account. These scenarios will be considered and analyzed in the subsequent sections.

# IV. Transfers in CR3BP

In this section, the two-impulse transfers are computed in the CR3BP. The global structure and typical types of planar transfer solutions are demonstrated, followed by the analysis of departure and insertion points and the comparison between different initial and final orbits. To extend the investigation to 3D ROs, nonplanar transfer cases are also considered.

# A. Global Solution

The planar transfer solutions from DROs to ROs are plotted in Fig. 6, with the horizontal axis representing the transfer time and the vertical axis representing the total impulse cost. Thousands of transfer trajectories are obtained through the optimization algorithm, and each trajectory corresponds to one point in the solution plane. Despite the discontinuity of the solutions in the solution plane due to the discretization of the initial orbits during the search phase, there still exist some structures referring to families of transfer orbits which comprise adjoining points. Connecting multiple transfer orbit families can form the Pareto front of transfer problems, indicating the best balance between time and fuel. It can be observed that with the increase of transfer time, the optimal impulse first decreases rapidly and eventually stabilizes at the global minimum value.

![](images/0851d7e5012fef70a04d1be4e53d9465ad51708796deb7e1bc7118fcec796fbf.jpg)  
a) 2:1 DRO to 3:2 RO

![](images/12c916cf66d78ff115319cd3562abaa028ac46c9a0c259e1a5e9e103cd39c36f.jpg)  
b) 3:1 DRO to 3:2 RO

![](images/6bbedb229e4bd1f068104c9265168cc2f082982dd88ecf79590f1ac4cd188fb1.jpg)  
c) 2:1 DRO to 3:1 RO

![](images/0c3b3244438bf19b3e66b2a3671cffdf15ceda0bb33de278d7ffc480630f2f62.jpg)  
d) 3:1 DRO to 3:1 RO  
Fig. 6 The solution planes from DROs to ROs in the CR3BP.

Two families of minimum-time transfer orbits departing from the 2:1 DRO are depicted in Figs. 7a and 7c as examples. The trajectories within the same family exhibit similar geometry and adjacent departure points, and the positions of insertion points in the final orbit are also relatively close. Different colors of the transfer orbits represent varying total impulse cost. For a deeper understanding of the transfer orbit family, in Figs. 7b and 7d, the solutions of one family are plotted separately in a solution plane as a detailed illustration of Figs. 6a and 6c and colored by its Jacobi constant. It can be noticed that the trend of the total impulse cost variations over the transfer time differ among distinct transfer orbit families. It could follow a monotonic change, as shown in Fig. 7d, or it may not be monotonic, as shown in Fig. 7b. The variations between the transfer time and the impulse cost are influenced by multiple factors, such as the characteristics of initial and final orbits, the collision with the primaries, and the type of transfer orbits. Nevertheless, each transfer orbit family has a minimum value of the cost which is the local optimal solution.

# B. Typical Transfer Types

The transfer orbits could be classified based on the distribution in the solution plane and the characteristics of the trajectories. Direct transfers, existing in the far left of the solution plane, are characterized by short transfer time, typically less than 20 days. Both of the transfer orbit families depicted in Fig. 7 belong to the direct transfer, and several other representative transfer orbits, located in the Pareto front of Fig. 6, are shown in both the Earth-moon rotating frame and the Earth-centered inertial frame in Fig. 8. In the Earth-moon rotating frame, the black points indicate the Earth and the moon, while in the Earth-centered inertial frame, the black point indicates the Earth, and the dashed circle refers to the orbit of the moon. It can be seen that, regardless of the initial or final orbits, such transfers move in a nearly elliptical orbit in the inertial frame and perform less than a complete revolution around the Earth. The characteristics of the representative transfer orbits, including the transfer time, departure impulse, insertion impulse, and total cost are listed in Table 4.

![](images/20bf7657661946f57a208f7d4b3ca30c72672464d29b46d32283359600fe1d82.jpg)

![](images/3b90992b2fdce2aecb7ffa6035649d7d6125b6d2459879e1736f377d6bfc7607.jpg)  
b) Solution plane of the transfer orbit family

![](images/04524eb6bf8e7c695285d7618240ec1659607696794c25d914bd37e60483d348.jpg)  
a) 2:1 DRO to 3:2 RO

![](images/73eda385f4de4dc462835269d061a4f15cecd550a09f6a8fc146b751075b3fd8.jpg)  
d) Solution plane of the transfer orbit family   
Fig. 7 Two transfer orbit families and their solution planes.

![](images/3bd9e09b82d0577087a1b3c623c6e9e5330e69ac718495613cc68c83c0a3a012.jpg)  
c) 2:1 DRO to 3:1 RO

![](images/affda11ce02978738d09398ed5f2e05dec9f9ddf8100e673742c89a61281a142.jpg)

![](images/ae34bacdf216f67cb3e9dece5fa8e0470087a77fe9671ce04d8deaa613ff5298.jpg)

![](images/1071aa84c6a3c003185cd8a6c9cdbe8abcd9cd6c0e55aa11585c2154370f1b5c.jpg)  
b) 3:1 DRO to 3:2 RO

![](images/0a28a81360522bb51f4a2e2229948578eff8adc7eb337aae37e5202976e0caff.jpg)  
a) 2:1 DRO to 3:2 RO

![](images/381a5c653e3876b5abe1c372ef89b3de5c8329dc672cace2fdcadda5a83f129d.jpg)

![](images/c7c7fb00829be7b9f6bafdaa08af3bf3fd65c3aed94b4761741948c5e9ddc207.jpg)

![](images/856f513ff0a9709afa55af717ee17fa3007d0420938c92d3bf313c46296aad6a.jpg)  
Fig. 8 The representative solutions of direct transfers in the Earth-moon rotating frame (left) and the Earth-centered inertial frame (right).

c) 2:1 DRO to 3:1 RO

d) 3:1 DRO to 3:1 RO

Table 4 The characteristics of representative transfer orbits in different types   

<table><tr><td>Transfer type</td><td>No.</td><td>Transfer pathway</td><td>Δt, days</td><td>Δv1, m/s</td><td>Δv2, m/s</td><td>Δv, m/s</td></tr><tr><td rowspan="4">Direct transfer</td><td>1</td><td>2:1 DRO to 3:2 RO</td><td>18.040</td><td>239.049</td><td>70.241</td><td>309.290</td></tr><tr><td>2</td><td>3:1 DRO to 3:2 RO</td><td>17.002</td><td>269.933</td><td>52.459</td><td>322.392</td></tr><tr><td>3</td><td>2:1 DRO to 3:1 RO</td><td>10.259</td><td>486.942</td><td>75.914</td><td>562.856</td></tr><tr><td>4</td><td>3:1 DRO to 3:1 RO</td><td>10.046</td><td>493.274</td><td>76.019</td><td>569.292</td></tr><tr><td rowspan="4">LGA transfer</td><td>5</td><td>2:1 DRO to 3:2 RO</td><td>80.544</td><td>35.488</td><td>39.767</td><td>75.255</td></tr><tr><td>6</td><td>3:1 DRO to 3:2 RO</td><td>79.411</td><td>36.977</td><td>30.394</td><td>67.371</td></tr><tr><td>7</td><td>2:1 DRO to 3:1 RO</td><td>62.691</td><td>201.755</td><td>44.607</td><td>246.361</td></tr><tr><td>8</td><td>3:1 DRO to 3:1 RO</td><td>62.819</td><td>233.828</td><td>40.652</td><td>274.479</td></tr><tr><td rowspan="4">External transfer</td><td>9</td><td>2:1 DRO to 3:2 RO</td><td>71.288</td><td>546.702</td><td>187.901</td><td>734.603</td></tr><tr><td>10</td><td>3:1 DRO to 3:2 RO</td><td>64.698</td><td>579.178</td><td>203.028</td><td>782.206</td></tr><tr><td>11</td><td>2:1 DRO to 3:1 RO</td><td>100.908</td><td>202.292</td><td>122.208</td><td>324.501</td></tr><tr><td>12</td><td>3:1 DRO to 3:1 RO</td><td>104.387</td><td>328.198</td><td>223.478</td><td>551.676</td></tr></table>

The initial conditions in the Earth-moon rotating frame are presented in the Appendix.

Lunar gravity assisted (LGA) transfers are mainly located at the bottom of the solution plane, characterized by close lunar flyby segments in the trajectories that significantly alter the velocity direction. The representative solutions of LGA transfers located in the Pareto front of Fig. 6 are shown in Fig. 9, and the characteristics are also listed in Table 4. This type of transfer involves a relatively small impulse to depart from the initial DRO, followed by a period of arc in the cislunar space before encountering the moon, and after LGA, the spacecraft enters an elliptical orbit around the Earth and performs multiple revolutions to change the phase until getting insertion into the final RO. In comparison to the direct transfer, the LGA transfer reduces the impulse cost by over $200\mathrm{m / s}$ , although the transfer time is longer. Therefore, it is concluded that the lunar gravity assist could significantly decrease fuel consumption at the cost of extended transfer time in the transfer pathway from DROs to ROs.

Another intriguing type of transfer is the external transfer, with a limited number of solutions scattered throughout the solution plane, which could be filtered out through the apogee altitude. As shown in Fig. 10, the apogee altitude of this transfer type even exceeds three times the Earth-moon distance. After the departure from DRO, the trajectory enters a large elliptical orbit with a high apogee, remaining for a long duration beyond the lunar orbit. Then, it can insert into the RO directly near the perigee or leverage the lunar gravity to lower the apogee and adjust the orientation of the elliptical orbit in the inertial frame before insertion. The primary objective of studying the external transfer is to contrast it with the transfer in the subsequent four-body model.

The rest of solutions in the plane are mostly a combination of the three typical transfers, lacking optimality in terms of time or fuel. To summarize the transfer pathway from DROs to ROs, the departure

from a DRO normally involves a large impulse to enter directly into an elliptical orbit, or a small impulse to fly around the cislunar space and wait for the LGA. Besides, the insertion into a RO mainly involves moving in an elliptical orbit for a single or multiple revolutions and a small insertion impulse. Additionally, because both of the direct and LGA transfers are located in the Pareto front, the tradeoff between transfer time and cost can be equated to the choice of these two transfer types. If the aim is to achieve the orbital transfer expeditiously, the direct transfer would be chosen undoubtedly. When the transfer time is not the foremost consideration, or the fuel carried by the spacecraft is insufficient, the LGA transfer would be a better choice.

# C. Analysis of Departure and Insertion Points

Because our algorithm covers an extensive range across the search space, thousands of solutions have been obtained, and statistical analysis could be employed to characterize the properties of these solutions and find some patterns. The quartile map [48], as shown in Fig. 11, is used to analyze the distribution of the departure and insertion locations. Different colors represent different transfer pathways, and the vertical axis represents the distance from the departure and insertion point to Earth. The five horizontal lines, from bottom to top, denote the minimum value, lower quartile, median, upper quartile, and maximum value. Because the lines corresponding to the lower quartile, median, and upper quartile are all located in the upper half of the map, the solutions tend to concentrate near the apogees of the initial and final orbits statistically, suggesting that the departure and insertion points close to the apogees have more transfer opportunities. It is probably due to the lower velocity of the initial and final orbits at the apogees. Note that, normally, the minimum and maximum values of the quartile map for one transfer pathway correspond to the perigee and apogee altitude of the initial and final orbits, but for

![](images/f28805811f57acfab2a487490109ac4ccc0a67904c1dc284b6990e9a43c6f0c7.jpg)  
a) 2:1 DRO to 3:2 RO

![](images/39c3737f41117996fb7f81174d5fec258ad6406d66d7f17beff17b2c637f0c10.jpg)

![](images/2b97a97a6cdd77b832611464dfa9a967b5af83a124246715cd9ecd743c60930b.jpg)

![](images/e52e1d4566ee268d01eec5de596040819f7a67607ec7521e327383f53c2befbd.jpg)  
b) 3:1 DRO to 3:2 RO

![](images/709e633789cedf6cad0d0a07698ff1ec48ea61a1e645f9ee0d1bf07a3df612ed.jpg)

![](images/1fcb51bce7d68e8dabbec65b4e318808afd74a4793f833d4269294a27b4e59f0.jpg)  
c) 2:1 DRO to 3:1 RO  
d) 3:1 DRO to 3:1 RO  
Fig. 9 The representative solutions of LGA transfers in the Earth-moon rotating frame (left) and the Earth-centered inertial frame (right).

![](images/afe010fd1c6baec64cb2966152e6f62a0419496499e4aea41ecfb4616a99015f.jpg)

![](images/7888fd2dd4fc51c380bbd1764528da0f6642b66285eeb9448137d7cee38ce504.jpg)

![](images/0530ba50ca6e47ea879a8d4a05925f5a77d05cfd641023369beaef81dc9cd62d.jpg)

![](images/7cab138c8b07a674538cbda22a4e939a1a4c32670d4adf4a6beb1879d1fdac11.jpg)  
b) 3:1 DRO to 3:2 RO

![](images/89a4b9f33ddca6703533e755a4dc04def33f9f5e7562bbcfe05c2894b4bd64a0.jpg)  
a) 2:1 DRO to 3:2 RO

![](images/b8c1df626c38b96738bc2a408f47a8f66c9f484bd4b9c7564efce3b6fc8c6c55.jpg)

![](images/6f3ac9445c766934237c6873b6710be2b1344f57083d51f562716558c9cfbb84.jpg)

![](images/1a2ba7e12a7ba29f29b006b9a4f5c81711e776cde6ba3617cf6e89ce72ecc4df.jpg)  
d) 3:1 DRO to 3:1 RO

c) 2:1 DRO to 3:1 RO

![](images/bf827ccbaeab18c41ba7683aa781abbaaa1386d7216dd3019eab2e8fa411d712.jpg)  
Fig. 10 The representative solutions of external transfers in the Earth-moon rotating frame (left) and the Earth-centered inertial frame (right).

![](images/34f863f8982111dd9e70f169aa6badca0e592341d0f4641ac1d21cae39544348.jpg)  
Fig. 11 The quartile map of departure and insertion points in different transfer pathways (For all figures, “/nd”, corresponding to the nondimensional equations in Secs. II.A and II.B).

the pathway from 3:1 DRO to 3:1 RO, the minimum value of the distance from the departure point to Earth is much greater than the perigee altitude of 3:1 DRO, indicating that it is not always feasible to transfer from any position in a DRO. On the contrary, as illustrated on the right of Fig. 11, it is possible to get inserted into any position in a RO.

# D. Comparison Between Different Initial and Final Orbits

The typical solutions in the Pareto front of the four transfer pathways are displayed in Fig. 12. For the transfer pathway from different

![](images/a8f5e77be57ed55a42c8163643845ef1772fd8ac04d582ae9a09144351688ba7.jpg)  
Fig. 12 The typical solutions in the Pareto front of different transfer pathways.

DROs to the same RO, the geometry of the transfer trajectories is quite similar as shown in Figs. 8-10. Because of the different orbital energy of the initial DROs, the impulse cost possesses a slight deviation in the same transfer type, but the global minimal value for the impulse cost is very close. For the transfer pathway from the same DRO to different ROs, both the geometry and the impulse cost of the transfer trajectories vary significantly, which is mainly caused by the distinct orbital characteristics of the 3:1 and 3:2 ROs. For instance, the perigee altitude of the 3:2 RO is over three times higher than that of the 3:1 RO, while the apogees are situated outside and inside the lunar orbit, which may affect the velocity of insertion and the feasibility of LGA. The global minimal value of the 3:2 RO is more than $150\mathrm{m / s}$ lower than the 3:1 RO. Moreover, as a final orbit, the 3:2 RO could offer richer solutions, as shown in Fig 6. As stated previously, although both are ROs, the different resonance ratios have a remarkable impact on the transfer pathway.

# E. Nonplanar Transfer Cases

Two types of 3D ROs could be bifurcated from the planar RO, as stated in Sec. II.D. Therefore, the nonplanar transfer pathways from the 2:1 DRO to four 3D ROs listed in Table 2 are computed. The normal component of the departure impulse is involved in the optimization algorithm, and, meanwhile, to broaden the solution planes in nonplanar transfers, the modified velocity constraint in Eq. (17) is adopted.

The nonplanar transfer solutions from the 2:1 DRO to 3D ROs are plotted in Fig. 13. It is apparent that the number of direct transfer solutions is decreased, which is primarily attributed to the considerable magnitude or velocity in the $z$ direction of the insertion point

![](images/0821824b18adfbfcf9a12e0e165c8db93cecf292091e78c8eaeba33902c17db0.jpg)  
a) 2:1 DRO to 3:2 RRO

![](images/7a0fc15575ce3aea3a265b170671d997187a3969f8364f594c68684cce87aabb.jpg)  
b) 2:1 DRO to 3:2 ARO

![](images/fe1c4ae3816d3095ce8afd5533ca0793ccf64e902c62d2ed1a8c260fab987eda.jpg)  
c) 2:1 DRO to 3:1 RRO

![](images/8227f9fe9c5ccc62d889bdfbe61af14d068d8336029cfb7c4aad81cbdf90e904.jpg)  
d) 2:1 DRO to 3:1 ARO  
Fig. 13 The solution planes from 2:1 DROs to 3D ROs in the CR3BP.

for direct transfers. This necessitates a substantial normal departure impulse, which is constrained by the range of the search variable. Most transfer solutions in nonplanar cases, including the global minimum-fuel solution, are LGA transfers. The representative solutions of LGA transfers, located in the Pareto front of Fig. 13, are shown in Fig. 14, and the characteristics are listed in Table 5. The initial conditions in the Earth-moon rotating frame are presented in the Appendix. The advantage of LGA transfers in nonplanar cases lies in the ability to redistribute the velocity in different directions by the close lunar flyby, such as reducing the in-plane velocity while increasing the normal velocity to facilitate the nonplanar transfer. External transfers also exist in nonplanar cases but are not optimal in either time or fuel.

Compared with the planar transfers, the primary difference of the nonplanar transfers manifests in the inclusion of positional and velocity components in the $z$ direction. Therefore, it is crucial for nonplanar transfers to seek the sources of the $z$ -direction components. As shown in the preceding outcomes, two main sources have been uncovered: one through an initial normal component of the departure impulse and the other through an LGA segment to alter the direction of velocity. Because of the considerable in-plane velocity of the initial orbit, the former requires a relatively large impulse in the $z$ direction to increase the inclination of the transfer orbit. The latter is much more fuel-efficient because the direction of velocity could be significantly altered as long as the geometric relationship between the transfer orbit and the moon is appropriate.

A further analysis has been conducted to illustrate the differences between the two types of 3D ROs. Specifically, for RROs, the maximum amplitude in the $z$ direction occurs at the periapsis and apoapsis, while the $z$ -direction velocity is zero. On the contrary, for AROs, the periapsis and apoapsis have the maximum $z$ -direction velocity, lying within the $x - y$ plane. From the perspective of the inertial frame, 3D ROs are approximately elliptical orbits around the

Earth with different equivalent orbital elements. The argument of perigee of RROs differs by 90 or 270 deg from the right ascension of the ascending node, while for AROs, they differ by 0 or 180 deg. As such, the distinction between different transfer pathways is that the multiple elliptical revolutions before insertion vary according to the final 3D orbits.

# V. Transfers in BR4BP

In this section, the two-impulse transfer solutions are constructed in the BR4BP, and then the characteristics are explored and compared with the transfers in the CR3BP. Additionally, as a nontrivial perturbation force, the solar gravity and its impacts on the transfer orbits are discussed.

# A. Comparison with Transfers in CR3BP

Because the solar gravity is considered in the BR4BP, the initial phase of the sun is involved in the optimization algorithm. The planar transfer solutions from DROs to ROs in the BR4BP are plotted in Fig. 15. Compared with the results in the CR3BP, the structure of the solution planes is quite similar, while the number of transfer solutions in the BR4BP is more abundant. Apparently, the transfer families in the CR3BP are extended due to the different initial phases of the sun in the BR4BP. From the view of the global minimum value of the transfer cost, it decreases over $10\mathrm{m / s}$ for the pathway to the 3:2 RO and over $30\mathrm{m / s}$ for the pathway to the 3:1 RO after considering the solar gravity. Therefore, through reasonable design, the perturbation of the solar gravity could both enrich the solution plane and save the fuel consumption.

By taking the transfer pathway from the 2:1 DRO to the 3:2 RO as an example, the representative transfer orbits of the three types are shown in the Earth-moon rotating frame and the Earth-centered inertial frame in Fig. 16. It can be seen that the typical transfer

![](images/d683f5e0e5c1724766abc6e170fc7349154892841a39aa8de5e74b3368db7a5b.jpg)  
Fig. 14 The representative nonplanar solutions of LGA transfers from $x - y - z$ view and $x - y$ view in the Earth-moon rotating frame and the Earth-centered inertial frame (from the left to the right).

Table 5 The characteristics of representative nonplanar transfer orbits in the CR3BP   

<table><tr><td>Transfer type</td><td>No.</td><td>Transfer pathway</td><td>Δt, days</td><td>Δv1, m/s</td><td>Δv2, m/s</td><td>Δv, m/s</td></tr><tr><td>LGA transfer</td><td>1</td><td>2:1 DRO to 3:2 RRO</td><td>88.104</td><td>83.171</td><td>49.057</td><td>132.227</td></tr><tr><td>——</td><td>2</td><td>2:1 DRO to 3:2 ARO</td><td>65.530</td><td>88.203</td><td>77.888</td><td>166.091</td></tr><tr><td>——</td><td>3</td><td>2:1 DRO to 3:1 RRO</td><td>58.150</td><td>99.992</td><td>216.646</td><td>316.638</td></tr><tr><td>——</td><td>4</td><td>2:1 DRO to 3:1 ARO</td><td>45.186</td><td>302.258</td><td>82.205</td><td>384.463</td></tr></table>

types in the CR3BP also exist in the BR4BP, possessing similar geometry and transfer characteristics. Compared with the solutions in Table 4, the total impulse cost in Table 6 has a slight decrease for all transfer types. The initial conditions are presented in the Appendix. Because of the perturbation of the solar gravity, the Jacobi energy no longer remains constant, as shown in the right column of Fig. 16.

The external transfer in the BR4BP is most significantly influenced by the solar gravity, which is considered as the weak stability boundary (WSB-)like transfer. The WSB can be used to constructed low-energy transfers to the moon, requiring little or no fuel for capture into the lunar orbit [49]. It has been successfully applied to several space missions, such as the rescue of the Japanese mission

Hiten [50]. The external transfer from DROs to ROs in the BR4BP has many resemblances to the traditional WSB transfer, hence referred to as the WSB-like transfer. First, the geometric shape of the external transfer exhibits similar characteristics to the WSB transfer. The apogee of the transfer orbit is found to approach the sun-Earth L1 LPO and becomes visibly distorted in the sun-Earth rotating frame, as shown in Fig. 17. Second, the change of the Jacobi energy of the external transfer is dramatic, attributed to the long-time external motion in the dynamically sensitive region. Third, compared with the external transfer in the CR3BP, the solar gravity could save more than $280~\mathrm{m / s}$ in fuel consumption, demonstrating the fuel saving of the external transfer in the BR4BP. Additionally, unlike the WSB transfer that raises the orbit altitude to the lunar orbit, the

![](images/ae660c858b0bf6296716a590636c93784f4692b97bf09d4df24e47974ab8a2f2.jpg)

![](images/b05759fe105af578263d0ef94fbf8f9f8e83566816c3f2552c551813f72dffb5.jpg)  
b) 3:1 DRO to 3:2 RO

![](images/86d93832df038d9c11c2ebc9d70e1ac23c0836fd277a703303739e4230de3c5e.jpg)  
a) 2:1 DRO to 3:2 RO

![](images/1631258efcd79b75c3493a3ef3a0edf52b4325468efd9b7741b252bb1df85b35.jpg)  
d) 3:1 DRO to 3:1 RO

c) 2:1 DRO to 3:1 RO

![](images/8cb58b434033fe236e53f9f58e879a75e9cd534d521e575cb5e4ce04f7968328.jpg)  
Fig. 15 The solution planes from DROs to ROs in the BR4BP.

![](images/ce70a5e103b39d693f48a7593466b77b0b841f9ba6587048077edc35ebdf0d4f.jpg)

![](images/4dc3d50f9ae07b0907b1141d73e6c4a0fa8ff5415d978eb3313e49bb45bc393b.jpg)

![](images/03c89d31141fa225bb47094e805f14c7e29cb5ff57bd2742b7c9242707d5e3e6.jpg)  
a) Direct transfer

![](images/ece705651564aec6ab430ebe17c44b4a78f53d52c8cbc00531cbb8bbab291470.jpg)

![](images/4990f5e5f74dde09c1d27f994cd72a1cdbb0e4c2fd45c4114b4341ebf129edd5.jpg)

![](images/c24f98cf6b3c69cd94dd98803cd538371e690d993a4636072587f198a7829543.jpg)  
b) LGA transfer

![](images/f0a9cabfc6720e7a28aeb16cdf79930647f8cdfe549d8f34b31063f627b91428.jpg)

![](images/03754350e2b9dbbe762f4066c19214d003bdab490b7d52ccafa80e142f60658a.jpg)  
Fig. 16 The representative solutions in the Earth-moon rotating frame (left), in the Earth-centered inertial frame (middle), and the corresponding change of Jacobi energy with time (right).

c) External transfer

Table 6 The characteristics of representative planar transfer orbits in the BR4BP   

<table><tr><td>Transfer type</td><td>No.</td><td>Δt, days</td><td>Δv1, m/s</td><td>Δv2, m/s</td><td>Δv, m/s</td><td>θs0, rad</td></tr><tr><td>Direct transfer</td><td>1</td><td>18.183</td><td>211.080</td><td>63.179</td><td>274.258</td><td>3.492</td></tr><tr><td>LGA transfer</td><td>2</td><td>62.733</td><td>42.583</td><td>28.767</td><td>71.349</td><td>5.808</td></tr><tr><td>External transfer</td><td>3</td><td>69.586</td><td>220.585</td><td>230.104</td><td>450.689</td><td>3.661</td></tr></table>

![](images/e859c6bbbfc6457a3525fa2e5f53a78dcb672e1e95412cc78d7123114c4a234d.jpg)  
Fig. 17 The representative solution of the external transfer in the sun-Earth rotating frame.

external transfer uses the solar gravity to lower the perigee altitude of the orbit from the altitude of a DRO to the perigee altitude of a RO, as shown in the middle of Fig. 16c.

# B. Analysis of Initial Solar Phases

As mentioned before, the solar gravity has a great impact on the transfer orbit. To gain a deeper understanding of the impact of the initial solar phase, a continuation method is adopted to obtain the transfer orbit family with different initial solar phases from the same departure point. By selecting any solution as the first transfer orbit in Fig. 15 and slightly increasing or decreasing the initial solar phase, the second transfer orbit could be obtained through the optimization phase in Sec. III.B. The solution in the first transfer orbit works as the initial condition in the optimization phase for the second transfer orbit, and this process is continued to generate the complete transfer orbit family.

Figure 18 displays the direct transfer family, the LGA transfer family, and the external transfer family corresponding to Fig. 16. Each transfer family is from the same departure point, while the transfer orbits are colored by different initial solar phases. In a transfer family, the transfer orbits maintain similar geometry, and the initial solar phase slightly impacts the position of the insertion point. The range of the color bar represents the interval within which the initial solar phase can be continued. The direct transfer family has the largest range, that is, approximately 1.2 rad, and the external transfer family has the smallest range, merely 0.06 rad. The smaller the range, the more sensitive the transfer orbit is with respect to the

![](images/7cb1b1381f8458c6cee23373790519e103f44176a9957e27e6d863a380baec9b.jpg)  
a) The direct transfer family

![](images/e43153045224197b232ff2674c4e2e190b159a9d94524413c14a2f949ce0640e.jpg)  
b) Solution plane of the direct transfer family

![](images/b3bd30f8311ca789805d95a68dce9dcafe67d006ba9720f6dd50666061338a1e.jpg)  
c) The LGA transfer family

![](images/bfc4889094b7a2c86a57ffad50ba7eb4ea4d079d626a455691d89f16122dceca.jpg)  
d) Solution plane of the LGA transfer family

![](images/4fc06f51f7f7112f7cc70cb1f15576354c7205fcf7e03d65651ff6e09a675bfa.jpg)  
e) The external transfer family

![](images/01a8a53fc720054c5224f24d6c4d74f53972d387f272ff1b64f16ab8ab55c34d.jpg)  
Fig. 18 The transfer orbit families and the corresponding solution planes.

f) Solution plane of the external transfer family

solar phase. Therefore, it is considered that the LGA and external transfers are more sensitive than the direct transfer. Moreover, the solution planes of the transfer orbit families are depicted in the right column in Fig. 18. Note that the initial solar phase could have an impact of up to $120\mathrm{m / s}$ on the transfer cost and within 3 days on the transfer time. In other words, with an appropriate initial solar phase, the transfer cost could decrease over $120\mathrm{m / s}$ in comparison to the ineffective transfer.

# VI. Transfers in Ephemeris Model

Several perturbations exist in real mission scenarios. Thus, the nominal trajectories designed in the CR3BP and the BR4BP need to be modified in the high-fidelity model. In this section, the differential correction scheme [51] is employed to maintain the shape of the nominal orbit and the continuity of motion in the ephemeris dynamical model. Three types of transfer orbits are separately transitioned and analyzed.

# A. Transition Scheme

Because of the coupling of state and epoch, a fixed-time multiple shooting method is adopted to ensure the convergence of the transition. Specifically, several revolutions of the initial orbit, the

Table 7 The success rate of the transition scheme   

<table><tr><td></td><td colspan="3">Success rate of different transfer time</td></tr><tr><td>Initial guess</td><td>0~50 days</td><td>50~100 days</td><td>100~150 days</td></tr><tr><td>CR3BP</td><td>80.0%</td><td>44.8%</td><td>38.4%</td></tr><tr><td>BR4BP</td><td>80.8%</td><td>49.6%</td><td>42.6%</td></tr></table>

transfer trajectory, and several revolutions of the final orbit are separately corrected for position continuity, and then the departure and insertion impulses are calculated from the velocity difference at the connection nodes. It is notable that for the transition from the CR3BP to the ephemeris model the departure epoch could be selected arbitrarily, yet for the transition from the BR4BP, the relative position of the moon and the sun at the departure epoch should be matched to the solar phase from the initial guesses [52].

To validate the efficacy of the transition scheme, a random sampling is conducted in the solution space in Figs. 6a and 15a. The solutions are first divided into different groups according to the transfer time, and then 500 solutions are randomly selected for ephemeris transition from each group. The success rates of the transition scheme are displayed in Table 7. It can be observed that the initial guesses from the BR4BP possess higher success rates than those from the CR3BP. Apparently, by incorporating the initial solar phase, the quality of the initial guesses for the transfer trajectory is increased. The success rates of the scheme exceed $80\%$ for the transfers within 50 days. On the contrary, the success rates are relatively low for the transfers more than 50 days including the LGA transfer and the external transfer; nevertheless, selecting the initial guesses from the BR4BP could enhance the success rates by over $4\%$ .

# B. Transition of Typical Transfer Types

The direct transfer is first transitioned into the ephemeris model. Because of the shorter transfer time and the insensitivity to the initial solar phase, the initial guesses for the transition are selected from the CR3BP. Take the transfer orbit number 1 from the 2:1 DRO to the 3:2 RO in Table 4 as an example. The converged trajectory with the departure epoch of 1 January 2025 is shown in both the

![](images/dd8f6f33d8f9ba2a702cb2af59cd89d0b390bad8f9d10ccf73267a946ce446f6.jpg)

![](images/c16be2bf29012afec56f9d54664edeb48dfc6f1dab6d85cfd9f9c8d4c4825639.jpg)  
Fig. 19 The converged trajectory of the direct transfer in the ephemeris model.

![](images/8f99ecb8f7f9c956945524545e5ee61edd248a3b172fd0b83260a80beccba4c1.jpg)  
Fig. 20 Variations in transfer cost of the direct transfer with departure epochs of every day in January 2025.

Earth-moon rotating frame and the Earth J2000 frame in Fig. 19, and its transfer time and cost are 17.866 days and $303.564\mathrm{m / s}$ respectively. It can be seen that in the rotating frame, the initial orbit, the transfer orbit, and the final orbit all retain their geometries, compared with Fig. 8a. For further analysis, the departure epoch is set as every day in January 2025 and the first day of every month in 2025. Because of the fixed-time multiple shooting method, the transfer time of the trajectory is invariant. The departure, insertion, and total impulse are depicted as a function of different departure epochs in Figs. 20 and 21. The black lines highlight the impulse values for the initial guess from the CR3BP. Note that the impulse has short-term fluctuations within a month and long-term fluctuations within a year. Different departure epochs could lead to a

variation of the impulse exceeding $100\mathrm{m / s}$ for direct transfers, and the cost could decrease nearly $30~\mathrm{m / s}$ compared with the CR3BP when the departure epoch is appropriate.

The LGA transfer and the external transfer are also transitioned into the ephemeris model with the initial guesses selected from the BR4BP. Take the transfer orbits numbers 2 and 3 from the 2:1 DRO to the 3:2 RO in Table 6 as examples. The converged trajectories are drawn in Figs. 22 and 23, with the departure epoch of 1709 hrs, 16.023 seconds on 31 January 2025 and 1800 hrs, 57.496 seconds on 10 February 2025, the transfer time of 62.129 days and 68.916 days, and the transfer cost of $320.821\mathrm{m / s}$ and $547.763\mathrm{m / s}$ , respectively. For practical reasons, the solar phase in the BR4BP is matched to only one departure epoch in a specific month of a year. Thus, the external

![](images/e31a560530eabb5c0a4c893c53c1a8fbb8c30f85f2b6217423040ce0075563c8.jpg)  
Fig. 21 Variations in transfer cost of the direct transfer with departure epochs of the first day of every month in 2025.

![](images/b0c62f951d5e9c87c836b7ffdc39fa68057b3ea0ebd8fc425c605ead0123fbaa.jpg)  
a) Orbits in the Earth-Moon rotating frame

![](images/482a983b4de6c6d7517d42369bee047967a00a9ab3015d38c83072a6d7276021.jpg)  
b) Orbits in the Earth J2000 frame   
Fig. 22 The converged trajectory of the LGA transfer in the ephemeris model.

![](images/c9ea2a8dae2635c81adcbe6e45ae8fbf462a4e3b5246998655e5e4c49cb3e14b.jpg)  
a) Orbits in the Earth-Moon rotating frame

![](images/ad322e988933f0781b4743ad9934b9d9855956a3929ca98d51b06af2b51d459a.jpg)  
b) Orbits in the Earth J2000 frame   
Fig. 23 The converged trajectory of the external transfer in the ephemeris model.

![](images/ffec86dc74b1874cdb1f5778eca4ee88ae7ec9f6ed6d70a4455c73ce2de689a1.jpg)  
Fig. 24 Variations in transfer cost of the external transfer with every matched departure epoch in 2025.

transfer is further transitioned with every matched epoch in 2025 and the departure, insertion, and total impulse are depicted in Fig. 24. It can be observed that the transfer orbits require more fuel consumption in the ephemeris model than in the BR4BP. For other mismatched departure epochs, the impulse may significantly increase, even resulting in nonconvergence of the transfer trajectory.

# VII. Conclusions

In this research, the transfer pathway from DROs to ROs has been designed. Different planar DROs, and planar and 3D ROs with different resonance ratios are considered as the initial and final orbits, respectively. A two-step transfer design method, consisting of the search phase and the optimization phase, is proposed to design the two-impulse transfer orbits. The transfer design method could accommodate various dynamical models as well as nonplanar transfers.

The global structure of transfer pathways in the CR3BP has been revealed, and three typical transfer types have been obtained, including the direct transfer, the LGA transfer, and the external transfer. The direct transfer possesses the shortest transfer time, typically less than 20 days, while the LGA transfer appears to be fuel saving through the close lunar flyby at the cost of extended transfer time. The transfers with different departure points, insertion points, and initial and final orbits have been compared and analyzed. Results indicate that the positions close to the apogee may offer more transfer opportunities, and the ROs with different resonance ratios could have distinct transfer characteristics. As for the 3D final orbit, there are fewer solutions, and the LGA still plays an important role in reducing the fuel consumption.

The transfer has also been constructed in the BR4BP, and more abundant solutions have been calculated. All types of transfer exist after considering the perturbation of the solar gravity. The external transfer is considered as the WSB-like transfer because it could reduce the transfer cost by leveraging the solar gravity compared with the result in the CR3BP. Additionally, the LGA transfer and the external transfer have been found to be highly sensitive to the initial solar phase. Finally, several representative transfer orbits have been transitioned into the ephemeris model, and then the preliminary transfer design is validated. The geometry of the transfer orbits is preserved, and the transfer cost fluctuates with different departure epochs.

This paper establishes a novel transfer pathway in the cislunar space and broadens the possibilities for mission design related to DROs and ROs. Moreover, the method in this study could also be applicable to other transfer problems and have great potential in the construction of the cislunar space transfer network.

Appendix: Initial Conditions for Representative DRO-RO Transfers   
Table A1 Initial conditions in the Earth-moon rotating frame of the solutions presented in Table 4   

<table><tr><td>No.</td><td>x, nd</td><td>y, nd</td><td>z, nd</td><td>\(\dot{x}\), nd</td><td>\(\dot{y}\), nd</td><td>\(\dot{z}\), nd</td></tr><tr><td>1</td><td>1.012500</td><td>0.237955</td><td>0.0</td><td>0.581970</td><td>-0.126684</td><td>0.0</td></tr><tr><td>2</td><td>1.005003</td><td>0.149700</td><td>0.0</td><td>0.637376</td><td>-0.099545</td><td>0.0</td></tr><tr><td>3</td><td>1.118644</td><td>0.167931</td><td>0.0</td><td>0.568764</td><td>-0.714733</td><td>0.0</td></tr><tr><td>4</td><td>1.081641</td><td>0.105776</td><td>0.0</td><td>0.595106</td><td>-0.685030</td><td>0.0</td></tr><tr><td>5</td><td>0.809709</td><td>0.023364</td><td>0.0</td><td>0.031842</td><td>0.477950</td><td>0.0</td></tr><tr><td>6</td><td>1.097994</td><td>0.082939</td><td>0.0</td><td>0.240391</td><td>-0.410790</td><td>0.0</td></tr><tr><td>7</td><td>1.082779</td><td>-0.203826</td><td>0.0</td><td>-0.474475</td><td>-0.373629</td><td>0.0</td></tr><tr><td>8</td><td>1.065880</td><td>-0.121321</td><td>0.0</td><td>-0.490624</td><td>-0.413143</td><td>0.0</td></tr><tr><td>9</td><td>0.987729</td><td>-0.241172</td><td>0.0</td><td>-0.886874</td><td>-0.037188</td><td>0.0</td></tr><tr><td>10</td><td>0.979093</td><td>0.150731</td><td>0.0</td><td>0.941132</td><td>0.072192</td><td>0.0</td></tr><tr><td>11</td><td>0.818898</td><td>-0.082502</td><td>0.0</td><td>-0.166991</td><td>0.668960</td><td>0.0</td></tr><tr><td>12</td><td>0.917790</td><td>0.126863</td><td>0.0</td><td>0.573448</td><td>0.438987</td><td>0.0</td></tr></table>

Table A2 Initial conditions in the Earth-moon rotating frame of the solutions presented in Table 5   

<table><tr><td>No.</td><td>x, nd</td><td>y, nd</td><td>z, nd</td><td>x̂, nd</td><td>ŷ, nd</td><td>ẑ, nd</td></tr><tr><td>1</td><td>1.166798</td><td>0.069329</td><td>0.0</td><td>0.138103</td><td>-0.545430</td><td>-0.024160</td></tr><tr><td>2</td><td>1.163323</td><td>0.081821</td><td>0.0</td><td>0.162561</td><td>-0.535397</td><td>-0.036358</td></tr><tr><td>3</td><td>0.810750</td><td>-0.035695</td><td>0.0</td><td>-0.056674</td><td>0.553213</td><td>0.086740</td></tr><tr><td>4</td><td>1.065667</td><td>-0.215889</td><td>0.0</td><td>-0.579079</td><td>-0.362793</td><td>-0.057924</td></tr></table>

Table A3 Initial conditions in the Earth-moon rotating frame of the solutions presented in Table 6   

<table><tr><td>No.</td><td>x, nd</td><td>y, nd</td><td>z, nd</td><td>\(\dot{x}\), nd</td><td>\(\dot{y}\), nd</td><td>\(\dot{z}\), nd</td></tr><tr><td>1</td><td>1.003370</td><td>0.239646</td><td>0.0</td><td>0.558056</td><td>-0.085356</td><td>0.0</td></tr><tr><td>2</td><td>0.810049</td><td>-0.028002</td><td>0.0</td><td>-0.044222</td><td>0.552692</td><td>0.0</td></tr><tr><td>3</td><td>0.810750</td><td>-0.035695</td><td>0.0</td><td>-0.074056</td><td>0.722892</td><td>0.0</td></tr></table>

# Acknowledgments

This work is supported by the National Natural Science Foundation of China, grant number 11872007, and Strategic Priority Research Program of the Chinese Academy of Sciences, grant number XDA30010200.

# References

[1] Creech, S., Guidi, J., and Elburn, D., and Artemis, "An Overview of NASA's Activities to Return Humans to the Moon," 2022 IEEE Aerospace Conference (AERO), Inst. of Electrical and Electronics Engineers, New York, March 2022, pp. 1-7, https://doi.org/10.1109/AERO53065.2022.9843277   
[2] Zhang, P., Dai, W., Niu, R., Zhang, G., Liu, G., Liu, X., Bo, Z., Wang, Z., Zheng, H., Liu, C., et al., "Overview of the Lunar In Situ Resource Utilization Techniques for Future Lunar Missions," Space: Science & Technology, Vol. 3, June 2023, Paper 0037. https://doi.org/10.34133/space.0037   
[3] Broucke, R. A., "Periodic Orbits in the Restricted Three-Body Problem with Earth-Moon Masses," Jet Propulsion Lab. TR 32-1168, Pasadena, CA, Feb. 1968, p. 100.   
[4] Henon, M., “Numerical Exploration of the Restricted Problem, V,” Astronomy and Astrophysics, Vol. 1, 1969, pp. 223-238.   
[5] Bezrouk, C. J., and Parker, J., "Long Duration Stability of Distant Retrograde Orbits," AIAA/AAS Astrodynamics Specialist Conference, AIAA Paper 2014-4424, Aug. 2014, https://doi.org/10.2514/6.2014-4424   
[6] Whitley, R., and Martinez, R., "Options for Staging Orbits in Cislunar Space," 2016 IEEE Aerospace Conference, Inst. of Electrical and Electronics Engineers, New York, June 2016, pp. 1-9, https://doi.org/10.1109/AERO.2016.7500635   
[7] Condon, G. L., and Williams, J., "Asteroid Redirect Crewed Mission Nominal Design and Performance," SpaceOps 2014 Conference, AIAA Paper 2014-1696, 2014. https://doi.org/10.2514/6.2014-1696,   
[8] Mazanek, D. D., Merrill, R. G., Brophy, J. R., and Mueller, R. P., "Asteroid Redirect Mission Concept: A Bold Approach for Utilizing Space Resources," Acta Astronautica, Vol. 117, 2015, pp. 163-171. https://doi.org/10.1016/j.actaastro.2015.06.018   
[9] McComas, D. J., Carrico, J. P., Hautamaki, B., Intelisano, M., Lebois, R., Loucks, M., Policastri, L., Reno, M., Scherrer, J., Schwadron, N. A., et al., "A New Class of Long-Term Stable Lunar Resonance Orbits: Space Weather Applications and the Interstellar Boundary Explorer," Space Weather-the International Journal of Research and Applications, Vol. 9, No. 11, 2011, https://doi.org/10.1029/2011SW000704   
[10] Dichmann, D., Parker, J., Williams, T. W., and Mendelsohn, C. R., "Trajectory Design for the Transiting Exoplanet Survey Satellite," 24th International Symposium on Space Flight Dynamics (ISSFD), May 2014.   
[11] Vaquero, M., "Spacecraft Transfer Trajectory Design Exploiting Resonant Orbits in Multi-Body Environments," Ph.D. Dissertation, Purdue Univ., West Lafayette, IN, 2013.   
[12] Binder, A., and Arnas, D., “Reliable and Repeatabile Transit Through Cislunar Space Using 2:1 Resonant Spatial Orbits,” Journal of Guidance, Control, and Dynamics, Vol. 47, No. 9, 2024, pp. 1973–1979. https://doi.org/10.2514/1.G007800   
[13] Gupta, M., Howell, K., and Frueh, C., "Long-Term Cislunar Surveillance Via Multi-Body Resonant Trajectories," AAS/AIAA Astrodynamics Specialist Conference, AAS Paper 22-630, Springfield, VA, Aug. 2022.   
[14] Gupta, M., Howell, K., and Frueh, C., “Constellation Design to Support Cislunar Surveillance Leveraging Sidereal Resonant Orbits,” AAS/AIAA Space Flight Mechanics Meeting, AAS Paper 23-203, Springfield, VA, Jan. 2023.   
[15] Sadaka, N., Gupta, M., Howell, K., and Frueh, C., "Observing the Cislunar Surveillance Cone From Synodic Resonant Orbit Constellations," AAS/AIAA Astrodynamics Specialist Conference, AAS Paper 24-443, Springfield, VA, Aug. 2024.   
[16] Peng, C., Zhang, Y., and He, S., “3:1/3:2 Resonant Orbits Touring L3–L5 in cislunar space,” Advances in Space Research, Vol. 73, No. 5, 2024, pp. 2499–2514. https://doi.org/10.1016/j.asr.2023.12.007   
[17] Capdevila, L. R., Guzzetti, D., and Howell, K. C., “Various Transfer Options From Earth into Distant Retrograde Orbits in the Vicinity of the Moon,” AAS/AIAA Space Flight Mechanics Meeting, AAS Paper 14-467, Springfield, VA, Jan. 2014.   
[18] Zhang, R., Wang, Y., Zhang, C., and Zhang, H., “The Transfers from Lunar DROs to Earth Orbits via Optimization in the Four Body Problem,” Astrophysics and Space Science, Vol. 366, No. 6, 2021, p. 49. https://doi.org/10.1007/s10509-021-03955-1   
[19] Peng, C., Zhang, H., Wen, C., Zhu, Z., and Gao, Y., “Exploring More Solutions for Low-Energy Transfers to Lunar Distant Retrograde Orbits,” Celestial Mechanics and Dynamical Astronomy, Vol. 134,

No.1,2022,pp.1-38.   
https://doi.org/10.1007/s10569-021-10056-2   
[20] Yin, Y., Wang, M., Shi, Y., and Zhang, H., "Midcourse Correction of Earth-Moon Distant Retrograde Orbit Transfer Trajectories Based on High-Order State Transition Tensors," Astrophysics, Vol. 7, No. 3, 2023, pp. 335-349. https://doi.org/10.1007/s42064-023-0162-8   
[21] Zhang, R., Wang, Y., Zhang, H., and Zhang, C., “Transfers from Distant Retrograde Orbits to Low Lunar Orbits,” Celestial Mechanics and Dynamical Astronomy, Vol. 132, No. 8, 2020, p. 41. https://doi.org/10.1007/s10569-020-09982-4   
[22] Ren, J., Li, M., and Zheng, J., "Families of Transfers from the Moon to Distant Retrograde Orbits in Cislunar Space," Astrophysics and Space Science, Vol. 365, No. 12, 2020, p. 192. https://doi.org/10.1007/s10509-020-03901-7   
[23] Oshima, K., "The Use of Vertical Instability of L1 and L2 Planar Lyapunov Orbits for Transfers From Near Rectilinear Halo Orbits to Planar Distant Retrograde Orbits in the Earth-Moon System," Celestial Mechanics and Dynamical Astronomy, Vol. 131, No. 3, 2019, p. 14. https://doi.org/10.1007/s10569-019-9892-6   
[24] Zimovan-Spreen, E. M., and Howell, K. C., "Dynamical Structures Nearby NRHOs with Applications in Cislunar Space," AAS/AIAA Astrodynamics Specialist Conference, AAS Paper 19-808, Springfield, VA, Nov. 2019.   
[25] Wang, Y., Zhang, R., Zhang, C., and Zhang, H., “Transfers Between NRHOs and DROs in the Earth-Moon System,” Acta Astronautica, Vol. 186, 2021, pp. 60-73. https://doi.org/10.1016/j.actaastro.2021.05.019   
[26] Muralidharan, V., and Howell, K. C., "Stretching Directions in Cislunar Space: Applications for Departures and Transfer Design," Astrophysics, Vol. 7, No. 2, 2023, pp. 153-178. https://doi.org/10.1007/s42064-022-0147-z   
[27] Capdevila, L. R., and Howell, K. C., "A Transfer Network Linking Earth, Moon, and the Triangular Libration Point Regions in the Earth-Moon System," Advances in Space Research, Vol. 62, No. 7, 2018, pp. 1826-1852. https://doi.org/10.1016/j.asr.2018.06.045   
[28] Conte, D., Di Carlo, M., Ho, K., Spencer, D. B., and Vasile, M., “EarthMars Transfers Through Moon Distant Retrograde Orbits,” Acta Astronautica, Vol. 143, 2018, pp. 372–379. https://doi.org/10.1016/j.actaastro.2017.12.007   
[29] Vaquero, M., and Howell, K. C., “Design of Transfer Trajectories Between Resonant Orbits in the Earth-Moon Restricted Problem,” Acta Astronautica, Vol. 94, No. 1, 2014, pp. 302–317. https://doi.org/10.1016/j.actaastro.2013.05.006   
[30] Vaquero, M., and Howell, K. C., "Leveraging Resonant-Orbit Manifolds to Design Transfers Between Libration-Point Orbits," Journal of Guidance, Control, and Dynamics, Vol. 37, No. 4, 2014, pp. 1143-1157. https://doi.org/10.2514/1.62230   
[31] Bonasera, S., and Bosanac, N., "Computing Natural Transitions Between Tori near Resonances in the Earth-Moon System," Journal of Guidance, Control, and Dynamics, Vol. 46, No. 3, 2023, pp. 443-454. https://doi.org/10.2514/1.G006941   
[32] Canales, D., Gupta, M., Park, B., and Howell, K. C., "A Transfer Trajectory Framework for the Exploration of Phobos and Deimos Leveraging Resonant Orbits," Acta Astronautica, Vol. 194, 2022, pp. 263-276. https://doi.org/10.1016/j.actaastro.2022.02.001   
[33] Anderson, R. L., "Approaching Moons from Resonance via Invariant Manifolds," Journal of Guidance, Control, and Dynamics, Vol. 38, No. 6, 2015, pp. 1097-1109. https://doi.org/10.2514/1.G000286   
[34] Yang, H., Hu, J., Bai, X., and Li, S., “Review of Trajectory Design and Optimization for Jovian System Exploration, Space,” Space: Science & Technology, Vol. 3, May 2023, Paper 0036. https://doi.org/10.34133/space.0036   
[35] Vaquero, M., and Howell, K. C., "Transfer Design Exploiting Resonant Orbits and Manifolds in the Saturn-Titan System," Journal of Spacecraft and Rockets, Vol. 50, No. 5, 2013, pp. 1069-1085. https://doi.org/10.2514/1.A32412   
[36] Pritchett, R., Zimovan, E., and Howell, Kathleen, "Impulsive and Low-Thrust Transfer Design Between Stable and Nearly-Stable Periodic Orbits in the Restricted Problem," 2018 Space Flight Mechanics Meeting, AIAA Paper 2018-1690, Jan. 2018.   
[37] Szebehely, V., Description of the Restricted Problem, Theory of Orbits: The Restricted Problem of Three Bodies, 1st ed. edition, New York, 1967, 7-41.

[38] Simó, C., Gómez, G., Jorba, Å., and Masdemont, J., The Bicircular Model Near the Triangular Libration Points of the RTBP, From Newton to Chaos, Vol. 336, 1995, pp. 343-370. https://doi.org/10.1007/978-1-4899-1085-1_34   
[39] Topputo, F., "On Optimal Two-Impulse Earth-Moon Transfers in a Four-Body Model," Celestial Mechanics and Dynamical Astronomy, Vol. 117, No. 3, 2013, pp. 279-313. https://doi.org/10.1007/s10569-013-9513-8   
[40] Peng, C., Shang, Y., He, S., Zhu, Z., and Wen, C., "Low-Energy Transfers to Lunar Distant Retrograde Orbits from Geostationary Transfer Orbits," Journal of Spacecraft and Rockets, Vol. 61, No. 5, 2024, pp. 1-12. https://doi.org/10.2514/1.A35623   
[41] Zimovan-Spreen, E. M., Howell, K. C., and Davis, D. C., "Dynamical Structures Nearby NRHOs with Applications to Transfer Design in Cislunar Space," Journal of the Astronautical Sciences, Vol. 69, No. 3, 2022, pp. 718-744. https://doi.org/10.1007/s40295-022-00320-4   
[42] Scheuerle, S. T., and Howell, K. C., "Tidal Attributes of Low-Energy Transfers in the Earth-Moon-Sun System," AAS/AIAA Astrodynamics Specialist Conference, AAS Paper 22-616, Springfield, VA, Aug. 2022.   
[43] Bruno, A. D., The Restricted 3-Body Problem: Plane Periodic Orbits," De Gruyter, 1994, https://doi.org/10.1515/9783110901733   
[44] Campbell, E. T., “Bifurcations From Families of Periodic Solutions in the Circular Restricted Problem with Application to Trajectory Design,” Ph.D. Dissertation, Purdue Univ., West Lafayette, IN, 1999.   
[45] Roy, A. E., and Ovenden, M. W., "On the Occurrence of Commensurable Mean Motions in the Solar System: The Mirror Theorem," Monthly Notices of the Royal Astronomical Society, Vol. 115, No. 3,

1955, pp. 296-309.  
https://doi.org/10.1093/mnras/115.3.296   
[46] Dichmann, D. J., Lebois, R., and Carrico, J. P., "Dynamics of Orbits Near 3: 1 Resonance in the Earth-Moon System," The Journal of the Astronautical Sciences, Vol. 60, No. 1, 2013, pp. 51-86. https://doi.org/10.1007/s40295-014-0009-x   
[47] Nocedal, J., and Wright, S. J., Numerical Optimization, Springer, New York, 2006, https://doi.org/10.1007/978-0-387-40065-5   
[48] Jia, J., He, X., and Jin, Y., Statistics," China Renmin Univ. Press, Beijing, 2009, pp. 89-90.   
[49] Belbruno, E., Gidea, M., and Topputo, F., "Weak Stability Boundary and Invariant Manifolds," SIAM Journal on Applied Dynamical Systems, Vol. 9, No. 3, 2010, pp. 1061-1089. https://doi.org/10.1137/090780638   
[50] Belbruno, E. A., and Miller, J. K., "Sun-Perturbed Earth-to-Moon Transfers with Ballistic Capture," Journal of Guidance, Control, and Dynamics, Vol. 16, No. 4, 1993, pp. 770-775. https://doi.org/10.2514/3.21079   
[51] Zhang, R., Wang, Y., Shi, Y., Zhang, C., and Zhang, H., "Performance Analysis of Impulsive Station-Keeping Strategies for Cis-Lunar Orbits with the Ephemeris Model," Acta Astronautica, Vol. 198, 2022, pp. 152-160. https://doi.org/10.1016/j.actaastro.2022.05.054   
[52] Boudad, K., Howell, K. C., and Davis, D. C., "Analogs for Earth-Moon Halo Orbits and Their Evolving Characteristics in Higher-Fidelity Force Models," AIAA Paper 2022-1276, Jan. 2022. https://doi.org/10.2514/6.2022-1276

P. Gurfil

Associate Editor