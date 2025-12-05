# GhostBBs User Manual

**Version:** 0.1.0 (Alpha)  
**License:** MIT Open Source

## Introduction

GhostBBs is a decentralized, privacy-focused bulletin board system built on peer-to-peer (P2P) networking principles. Unlike traditional social media or forums, GhostBBs has no central server. It enables users to create and participate in discussion boards with end-to-end encryption, ensuring data privacy and security.

![About Application Screen](Screenshot_2025-12-02_20-26-45.png)

### Key Features
* **Fully Decentralized:** No central server; the network relies on users.
* **End-to-End Encryption:** All communications are private.
* **P2P Synchronization:** Boards and posts sync directly between peers.
* **Multi-board Discussions:** Support for threaded conversations and file attachments.
* **Trust Controls:** Robust moderation and peer banning tools.

---

## 1. Getting Started

### Profile Creation and Login
Upon launching GhostBBs, you will be greeted by the Profile Selection screen. Because GhostBBs is decentralized, your "account" is actually a set of cryptographic keys stored locally on your device.

![Profile Selection Screen](Screenshot_2025-12-02_20-19-19.png)

* **Select Existing:** Click on an existing profile (e.g., "Default User") to log in.
* **Create New:** Click the **"Create new profile"** button to generate a new identity.
    * *Note: Your identity is secured with Ed25519 cryptographic keys.*

---

## 2. The Dashboard

Once logged in, you will see the Welcome Dashboard. This serves as the central hub for navigation.

![Welcome Dashboard](Screenshot_2025-12-02_20-26-21.png)

The dashboard provides quick access to the three main modules of the application:

1.  **Boards (BBS):** The core forum experience. Browse public boards, create your own, and participate in threaded discussions using Markdown.
2.  **Private Chat:** specific, encrypted direct messaging with other peers. Includes file sharing and forward secrecy.
3.  **Peers:** A network monitor to view connected nodes, manage trust, and view network health.

---

## 3. Network and Peer Management

The **Peer Monitor** is essential for maintaining a healthy and safe connection to the network. Since there is no central moderator, you are in control of who you connect with.

![Peer Monitor Screen](Screenshot_2025-12-03_23-11-53.png)

### Understanding the Monitor
At the top of the screen, you will see real-time statistics:
* **Connected:** Number of active peers you are currently syncing with.
* **Discovered:** Peers found on the network but not necessarily connected.
* **Trusted/Banned:** Your personal allow/block lists.

### Managing Peers
The list view provides detailed information on specific nodes:
* **Name/ID:** The unique identifier (Peer ID) is critical for verifying identity.
* **Status/Last Seen:** Helps troubleshoot connectivity issues.
* **Ban/Trust Switch:** You can toggle the **Ban/Trust** switch to "On" to trust a peer or block them.
* **Actions:** Click the chat bubble icon to immediately open a private encrypted channel with that specific peer.

---

## 4. Technical Support

**Identity Security** GhostBBs uses **Ed25519 cryptographic keys**. Ensure you back up your profile data locally, as there is no "password reset" email feature on a decentralized network.

**License** This software is provided 'as is', without warranty of any kind, under the **MIT License**.