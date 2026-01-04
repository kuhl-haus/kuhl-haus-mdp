<!-- These are examples of badges you might want to add to your README:
   please update the URLs accordingly 

[![ReadTheDocs](https://readthedocs.org/projects/kuhl-haus-mdp/badge/?version=latest)](https://kuhl-haus-mdp.readthedocs.io/en/stable/)
[![Conda-Forge](https://img.shields.io/conda/vn/conda-forge/kuhl-haus-mdp.svg)](https://anaconda.org/conda-forge/kuhl-haus-mdp)
[![Monthly Downloads](https://pepy.tech/badge/kuhl-haus-mdp/month)](https://pepy.tech/project/kuhl-haus-mdp)
-->


[![License](https://img.shields.io/github/license/kuhl-haus/kuhl-haus-mdp)](https://github.com/kuhl-haus/kuhl-haus-mdp/blob/mainline/LICENSE.txt)
[![PyPI](https://img.shields.io/pypi/v/kuhl-haus-mdp.svg)](https://pypi.org/project/kuhl-haus-mdp/)
[![Downloads](https://static.pepy.tech/badge/kuhl-haus-mdp/month)](https://pepy.tech/project/kuhl-haus-mdp)
[![Build Status](https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/publish-to-pypi.yml/badge.svg)](https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/publish-to-pypi.yml)
[![CodeQL Advanced](https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/codeql.yml/badge.svg)](https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/codeql.yml)
[![codecov](https://codecov.io/gh/kuhl-haus/kuhl-haus-mdp/branch/mainline/graph/badge.svg)](https://codecov.io/gh/kuhl-haus/kuhl-haus-mdp)
[![GitHub issues](https://img.shields.io/github/issues/kuhl-haus/kuhl-haus-mdp)](https://github.com/kuhl-haus/kuhl-haus-mdp/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/kuhl-haus/kuhl-haus-mdp)](https://github.com/kuhl-haus/kuhl-haus-mdp/pulls)
[![Documentation](https://readthedocs.org/projects/kuhl-haus-mdp/badge/?version=latest)](https://kuhl-haus-mdp.readthedocs.io/en/latest/)

# kuhl-haus-mdp

Market data processing pipeline for stock market scanner.



## TL;DR
Non-business Massive (AKA Polygon.IO) accounts are limited to a single WebSocket connection per asset class and it has to be fast enough to handle messages in a non-blocking fashion or it'll get disconnected.  The market data processing pipeline consists of loosely-coupled market data processing components so that a single WebSocket connection can handle messages fast enough to maintain a reliable connection with the market data provider.

Per, https://massive.com/docs/websocket/quickstart#connecting-to-the-websocket:
> *By default, one concurrent WebSocket connection per asset class is allowed. If you require multiple simultaneous connections for the same asset class, please [contact support](https://massive.com/contact).*

# Components Summary

Non-business Massive (AKA Polygon.IO) accounts are limited to a single WebSocket connection per asset class and it has to be fast enough to handle messages in a non-blocking fashion or it'll get disconnected.  The Market Data Listener (MDL) connects to the Market Data Source (Massive) and subscribes to unfiltered feeds. MDL inspects the message type for selecting the appropriate serialization method and destination Market Data Queue (MDQ).  The Market Data Processors (MDP) subscribe to raw market data in the MDQ and perform the heavy lifting that would otherwise constrain the message handling speed of the MDL.  This decoupling allows the MDP and MDL to scale independently.  Post-processed market data is stored in the MDC for consumption by the Widget Data Service (WDS).  Client-side widgets receive market data from the WDS, which provides a WebSocket interface to MDC pub/sub streams and cached data.

[![Market Data Processing C4-V1.drawio.png](docs/Market_Data_Processing_C4.png)]

# Component Descriptions

## Market Data Listener (MDL)
The MDL performs minimal processing on the messages.  MDL inspects the message type for selecting the appropriate serialization method and destination queue.  MDL implementations may vary as new MDS become available (for example, news).

MDL runs as a container and scales independently of other components. The MDL should not be accessible outside the data plane local network.

## Market Data Queues (MDQ)

**Purpose:** Buffer high-velocity market data stream for server-side processing with aggressive freshness controls
- **Queue Type:** FIFO with TTL (5-second max message age)
- **Cleanup Strategy:** Discarded when TTL expires
- **Message Format:** Timestamped JSON preserving original Massive.com structure
- **Durability:** Non-persistent messages (speed over reliability for real-time data)
- **Independence:** Queues operate completely independently - one queue per subscription
- **Technology**: RabbitMQ

The MDQ should not be accessible outside the data plane local network.

## Market Data Processors (MDP)
The purpose of the MDP is to process raw real-time market data and delegate processing to data-specific handlers.  This separation of concerns allows MDPs to handle any type of data and simplifies horizontal scaling.  The MDP stores its processed results in the Market Data Cache (MDC).

The MDP:
- Hydrates the in-memory cache on MDC
- Processes market data 
- Publishes messages to pub/sub channels
- Maintains cache entries in MDC

MDPs runs as containers and scale independently of other components. The MDPs should not be accessible outside the data plane local network.

## Market Data Cache (MDC)

**Purpose:** In-memory data store for serialized processed market data.
* **Cache Type**: In-memory persistent or with TTL
- **Queue Type:** pub/sub
- **Technology**: Redis

The MDC should not be accessible outside the data plane local network.

## Widget Data Service (WDS)
**Purpose**:
1. WebSocket interface provides access to processed market data for client-side code
2. Is the network-layer boundary between clients and the data that is available on the data plane

WDS runs as a container and scales independently of other components.  WDS is the only data plane component that should be exposed to client networks.


## Service Control Plane (SCP)
**Purpose**: 
1. Authentication and authorization
2. Serve static and dynamic content via py4web
3. Serve SPA to authenticated clients
4. Injects authentication token and WDS url into SPA environment for authenticated access to WDS
5. Control plane for managing application components at runtime
6. API for programmatic access to service controls and instrumentation.

The SCP requires access to the data plane network for API access to data plane components.

