# DATA3001 Group Project

## Project Status

**Current stage:** Week 1 — topic selection and project scoping

The group is currently considering two possible research directions:

1. **Where Things End Up**
2. **Drifter Prediction**

No final topic, study region, prediction horizon, or modelling method has been selected. This README records the current understanding of both directions so that all group members can review the same starting point.

## Ocean Currents and Transport Pathways

Surface currents create **dominant transport pathways** that constrain and influence where floating objects or materials are likely to move.

![Conceptual sketch of directional surface-current pathways](docs/images/ocean-current-pathways.png)

*Figure 1. Conceptual illustration of transport between points A and B under an assumed dominant surface-current pattern. The green path is more consistent with the sketched flow, while the blue and orange paths are less consistent with it. This is an explanatory sketch rather than a geographic or dynamical map.*

The highway analogy helps illustrate the main direction of transport, but ocean currents are not fixed lanes. Actual trajectories can spread around the dominant flow because currents vary across space and time. Wind, waves, eddies, and the properties of the drifting object may also affect its movement.

## Candidate Direction 1: Where Things End Up

**Research question:** Given a release location and a specified lead time, where is floating material likely to be transported?

Possible examples include:

- an oil slick;
- a liferaft;
- floating debris or a container; and
- a surface drifter.

This direction studies a **distribution of possible future locations** and the transport relationships between different parts of the study region. Its objective is not to predict one exact route for one object.

![Conceptual destination-likelihood map from release point A](docs/images/where-things-end-up-likelihood.png)

*Figure 2. Conceptual illustration of a future-location distribution from release point A at a chosen forecast horizon. Green represents relatively high likelihood, yellow represents lower likelihood, and red represents very low likelihood under the assumed current pattern. The colours are illustrative and do not represent observed data, calibrated probabilities, or the output of a fitted model.*

A possible analytical product would include:

- a surface-transport operator, such as a transition matrix or a similar representation;
- destination-likelihood maps for selected release points and lead times;
- transport relationships between different parts of the study region; and
- identification of areas where floating material tends to accumulate or leave the region.

## Candidate Direction 2: Drifter Prediction

**Research question:** Given the recent track of an individual drifter, where will that drifter be after a specified period?

This direction focuses on forecasting the future position or trajectory of a **single drifter**. It is a near-term prediction problem that may be approached using statistical or machine-learning models.

A possible analytical product would include:

- predicted positions or trajectories for held-out drifters;
- forecast error measured across different lead times;
- a clearly documented training and testing split; and
- comparison with simple baselines, including continued present velocity and movement following the estimated mean flow.

## Difference Between the Two Directions

**Where Things End Up** estimates regional transport and a distribution of possible destinations from a release point.

**Drifter Prediction** uses the recent track of one drifter to forecast that individual drifter's future position.

The first direction has a broader regional and distributional focus. The second has a narrower individual-trajectory forecasting target.

## Current Decision State

The group is currently leaning towards **Where Things End Up**.

The project will first focus on the **Florida–Bahamas** region and then extend the analysis to the broader **Gulf Stream** region.

We will first conduct a **spatial transition coverage check** for Florida–Bahamas to assess whether there are enough historical drifter trajectories to support reliable destination-likelihood maps. The same framework can then be extended to the broader Gulf Stream region.
