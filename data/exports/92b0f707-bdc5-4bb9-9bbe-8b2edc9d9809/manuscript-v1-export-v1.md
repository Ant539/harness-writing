# Graph Partitioning and Computation-Overhead-Aware Load Balancing for Sharded Blockchains

## Introduction

\noindent
Sharding is one of the main approaches to scaling blockchain systems because it distributes state and transaction processing across multiple shards. Prior systems have shown that shard-based architectures can improve throughput while preserving decentralization and security assumptions \cite{luu2016secure,kokoris2018omniledger,zamani2018rapidchain,wang2019monoxide,hong2021pyramid,li2022jenga}. In practice, however, the gain from parallel execution depends not only on how many shards are created, but also on how accounts and contracts are placed across them. When strongly interacting accounts are separated, the system incurs additional cross-shard communication and coordination cost; when computationally expensive contracts accumulate in only a few shards, those shards become stragglers and constrain end-to-end throughput.

This placement problem is especially difficult in smart-contract-centric workloads. Account interactions are highly skewed and time-varying, and the execution cost of transactions can differ substantially even when their counts are similar. A reconfiguration policy that relies only on transaction volume, account popularity, or historical access frequency may therefore misjudge the true processing pressure of a shard. The resulting assignment can appear balanced at the transaction level while remaining unbalanced at the execution level. In practice, this mismatch leads to persistent local hotspots, longer shard processing time, more cross-shard transactions, and growing mempool backlog under high concurrency.

The core challenge is that shard reconfiguration must satisfy two objectives that naturally conflict. Moving accounts away from overloaded shards can reduce load skew, but aggressive migration may split interaction-heavy account groups and increase cross-shard overhead. Conversely, preserving interaction locality alone can cluster high-gas accounts and contracts inside a few shards. What is needed is a reconfiguration objective that captures both sides of the problem: the heterogeneity of actual execution pressure and the communication implications of account partitioning.

This paper addresses that need with a graph-partitioning and computation-overhead-aware load-balancing mechanism for sharded blockchains. For each epoch, active accounts are organized into a temporal interaction graph whose edge weights combine interaction frequency and gas usage. Account load and shard capacity are estimated with exponential moving averages so that short-lived bursts do not dominate the next reconfiguration decision. On this basis, account placement is formulated as a joint optimization problem that minimizes shard-pressure variance and normalized cross-shard cut cost under assignment and migration-budget constraints. Since the resulting formulation is difficult to solve exactly within an epoch-level reconfiguration window, the paper further develops a priority-queue-based heuristic migration algorithm that evaluates candidate moves by both load-relief benefit and interaction-preservation gain while updating only the affected local neighborhoods after each accepted migration. The intended contribution is therefore not a new sharding protocol, but a reconfiguration model in which interaction locality and gas-based execution burden are represented within the same decision objective and followed by one practical migration policy.

The main contributions of this paper are summarized as follows.
\begin{itemize}
    \item A temporal account-interaction model is developed for epoch-level reconfiguration, in which edge weights jointly encode interaction frequency and cumulative gas consumption so that communication intensity and execution overhead are represented in a single graph structure.
    \item A computation-aware shard-pressure model is introduced by combining exponential moving averages of account gas volume and shard effective capacity, and the resulting assignment problem is formulated as a joint objective over load variance and normalized cross-shard cut cost.
    \item A practical heuristic migration algorithm is designed for the resulting constrained assignment problem. The algorithm uses a priority queue and local differential evaluation to rank candidate migrations efficiently and to avoid expensive global recomputation after each accepted move.
    \item A trace-driven empirical evaluation on 500,000 Ethereum Mainnet transactions is conducted in BlockEmulator to examine load distribution, shard processing time, throughput, and mempool backlog under multiple bandwidth, workload, and shard-count settings.
\end{itemize}

## Related Work

Research on sharded blockchains can be broadly grouped into protocol architecture, state assignment and balancing, and cross-shard coordination optimization. Early sharding systems, including the secure sharding protocol of Luu et al., OmniLedger, RapidChain, and Monoxide, established the feasibility of scaling blockchain execution through partitioned state and parallel processing \cite{luu2016secure,kokoris2018omniledger,zamani2018rapidchain,wang2019monoxide}. Later systems such as Pyramid and Jenga further explored layered architectures and more effective support for contract execution \cite{hong2021pyramid,li2022jenga}. These studies show that sharding can improve system capacity, but they also make clear that performance depends heavily on how state is partitioned and reconfigured over time.

The second line of work studies state assignment and runtime balancing. Okanami et al. investigated load balancing and later extended the idea to protocol-level and wallet-level account assignment \cite{okanami2020load,okanami2022load}. Li et al. studied state sharding with the goal of improving scalability while maintaining load balance across shards \cite{li2022achieving}. LB-Chain made account migration more explicit as a runtime balancing mechanism \cite{li2023lb}. These studies are closely related to the present paper because they recognize that static assignment is insufficient under changing workloads. Their common limitation, however, is that load is usually approximated by coarse indicators such as transaction counts, account access frequency, or aggregate historical activity. Such proxies are useful, but they do not directly capture the heterogeneity of smart-contract execution cost or the fact that interaction preservation and execution balancing must be handled together during reconfiguration. In particular, LB-Chain is the closest migration baseline in spirit, whereas the present work differs by driving migration with one graph model that jointly encodes interaction structure and gas-based execution burden rather than ranking candidates from communication or load indicators alone.

The third line of work focuses on cross-shard overhead and system stress. BrokerChain reduces the cost of account/balance-based state sharding by refining cross-shard transaction handling \cite{huang2022brokerchain}. Presto optimizes cross-shard transaction execution in sharded architectures \cite{ding2024presto}. ContribChain incorporates node-contribution awareness into stress-balanced sharding \cite{huang2025contribchain}. These systems improve important parts of the sharding pipeline, but their primary focus is not the joint assignment problem studied here, namely how to rebalance accounts so that shard pressure is reduced without sacrificing interaction locality.

This paper sits at the intersection of these lines of work. Similar to prior balancing methods, it treats reconfiguration as an account-placement problem; similar to cross-shard optimization work, it explicitly accounts for the cost of cutting interacting account groups. The key difference is that the reconfiguration decision itself is driven by a graph that encodes both interaction structure and gas-based execution pressure, and the assignment is optimized with one migration-budgeted objective over load variance and cross-shard cost. The contribution is therefore not a new sharding protocol, but a more faithful and practically targeted reconfiguration model for smart-contract workloads, especially when transaction counts alone are a weak proxy for execution burden.

## System Model and Problem Formulation



### Notation and Active Account Set

Consider a sharded blockchain system with $K$ shards. Let $t$ denote the current epoch and let $B_t$ denote the set of confirmed transactions in that epoch. Here, $B_t$ includes both successfully executed and reverted on-chain transactions, because reverted smart-contract calls still consume gas and occupy execution resources. Let $\tau$ be the sliding-window length used to identify active accounts, let $V^t$ be the active-account set, let $G^t=(V^t,E^t,M^t)$ be the temporal account interaction graph, and let $X^t=[x_{j,i}^t]$ be the account-to-shard assignment matrix. For later use, $g_j^t$ denotes the observed gas volume involving account $j$ in epoch $t$, $w_j^t$ denotes its predicted execution load, $L_i^t$ denotes the aggregate predicted load assigned to shard $i$, $c_i^t$ denotes the effective capacity estimate of shard $i$, $P_i^t$ denotes the resulting shard pressure, and $B_{\max}$ denotes the migration budget at one epoch boundary.

For an account $j$, define $\mathrm{TxCount}(j,s)$ as the number of confirmed transactions involving account $j$ in epoch $s$. An account is regarded as active in epoch $t$ if it participates in at least one confirmed transaction within a sliding window of length $\tau$:
\begin{equation}
V^t=\{j\mid \exists s\in [t-\tau+1,t],\ \mathrm{TxCount}(j,s)\ge 1\}.
\end{equation}

Accounts that remain inactive throughout the whole window are pruned as cold accounts. The window length $\tau$ therefore controls a tradeoff between retaining longer interaction history and keeping the graph compact enough for epoch-level reconfiguration.

### Temporal Account Interaction Graph

The account interaction graph at epoch $t$ is defined as
\begin{equation}
G^t=(V^t,E^t,M^t),
\end{equation}
where $E^t$ contains account pairs that interact within the sliding window $[t-\tau+1,t]$, and $M^t=\{e_{u,v}^t\mid (u,v)\in E^t\}$ stores the corresponding edge weights. An undirected graph is used because the reconfiguration objective is to preserve interaction locality between account pairs, rather than to distinguish which side initiated an individual transfer or contract call.

For any account pair $u,v\in V^t$, define the cumulative interaction frequency and cumulative gas volume over the same sliding window as
\begin{equation}
\begin{aligned}
\mathrm{Freq}_{u,v}^t
&=
\sum_{s=t-\tau+1}^{t}
\left|
\left\{
tx\in B_s \,\middle|\,
\substack{
(tx.from=u \land tx.to=v)\\
{}\lor(tx.from=v \land tx.to=u)
}
\right\}
\right|.
\end{aligned}
\end{equation}
and
\begin{equation}
\begin{aligned}
\mathrm{Vol}_{u,v}^t
&=
\sum_{s=t-\tau+1}^{t}
\sum_{\substack{
tx\in B_s:\\
(tx.from=u \land tx.to=v)\\
{}\lor(tx.from=v \land tx.to=u)
}}
tx.gasUsed.
\end{aligned}
\end{equation}

An undirected edge $(u,v)\in E^t$ exists if and only if $\mathrm{Freq}_{u,v}^t>0$. Since both interaction frequency and gas volume are typically long-tailed in blockchain workloads, a logarithmic transform is first applied:
\begin{equation}
\widehat{\mathrm{Freq}}_{u,v}^t=\ln(1+\mathrm{Freq}_{u,v}^t),
\end{equation}
\begin{equation}
\widehat{\mathrm{Vol}}_{u,v}^t=\ln(1+\mathrm{Vol}_{u,v}^t).
\end{equation}

To keep the two components on comparable scales, they are normalized as
\begin{equation}
\widetilde{\mathrm{Freq}}_{u,v}^t
=
\frac{\widehat{\mathrm{Freq}}_{u,v}^t}
{\max_{(a,b)\in E^t}\widehat{\mathrm{Freq}}_{a,b}^t+\varepsilon},
\end{equation}
\begin{equation}
\widetilde{\mathrm{Vol}}_{u,v}^t
=
\frac{\widehat{\mathrm{Vol}}_{u,v}^t}
{\max_{(a,b)\in E^t}\widehat{\mathrm{Vol}}_{a,b}^t+\varepsilon},
\end{equation}
where $\varepsilon>0$ is a small constant used to avoid division by zero. The final edge weight is then defined as
\begin{equation}
e_{u,v}^t
=
\alpha \widetilde{\mathrm{Freq}}_{u,v}^t
+
(1-\alpha)\widetilde{\mathrm{Vol}}_{u,v}^t,
\qquad
\alpha\in[0,1].
\end{equation}

Thus, each edge jointly reflects communication intensity and execution-related interaction burden. When $\alpha$ is larger, the graph emphasizes interaction frequency more strongly; when $\alpha$ is smaller, it places more weight on gas-aware execution significance.

### Computation-Aware Load and Shard Pressure Estimation

Let $X^t=[x_{j,i}^t]\in\{0,1\}^{|V^t|\times K}$ denote the account-to-shard assignment matrix in epoch $t$, where
\begin{equation}
x_{j,i}^t
=
\begin{cases}
1, & \text{if account } j \text{ is assigned to shard } i,\\
0, & \text{otherwise}.
\end{cases}
\end{equation}

For convenience, let
\begin{equation}
S^t(j)=i
\iff
x_{j,i}^t=1,
\end{equation}
that is, $S^t(j)$ denotes the shard currently assigned to account $j$.

Because shard load may fluctuate sharply from one epoch to the next, direct use of raw observations can amplify short-lived bursts and lead to unstable reconfiguration. Let
\begin{equation}
g_j^t
=
\sum_{\substack{
tx\in B_t:\\
tx.from=j \lor tx.to=j
}}
tx.gasUsed
\end{equation}
denote the observed gas volume involving account $j$ in epoch $t$. At the beginning of epoch $t$, the system has observed data only up to epoch $t-1$, so the predicted account load is estimated by an exponential moving average:
\begin{equation}
w_j^t
=
\rho g_j^{t-1}
+
(1-\rho)w_j^{t-1},
\qquad
\rho\in(0,1],
\end{equation}
with initialization $w_j^0=g_j^0$. Thus, $w_j^t$ is a prediction for the next reconfiguration round rather than a quantity computed from the still-unobserved workload of epoch $t$ itself.

The aggregate predicted load assigned to shard $i$ is then
\begin{equation}
L_i^t
=
\sum_{j\in V^t} x_{j,i}^t w_j^t.
\end{equation}

Similarly, let $B_i^{t-1}$ be the number of blocks produced by shard $i$ in the previous epoch and let $G_{\max}$ be the block gas limit. Then $B_i^{t-1}G_{\max}$ serves as an observable proxy for the processing capacity delivered by shard $i$ in the previous epoch. To keep the capacity estimate both smooth and conservative, the effective capacity of shard $i$ is estimated as
\begin{equation}
\begin{aligned}
c_i^t
&=
\eta\left(
\rho_c B_i^{t-1}G_{\max}
+
(1-\rho_c)c_i^{t-1}
\right),\\
&\rho_c\in(0,1],\ \eta\in(0,1].
\end{aligned}
\end{equation}

Here, $\rho_c$ is the smoothing factor for capacity estimation and $\eta$ is a conservative scaling coefficient. With initialization $c_i^0=\eta B_i^0 G_{\max}$, the corresponding shard pressure is defined as
\begin{equation}
P_i^t
=
\frac{L_i^t}{c_i^t+\varepsilon}.
\end{equation}

Let the average shard pressure be
\begin{equation}
\bar P^t
=
\frac{1}{K}\sum_{i=1}^{K}P_i^t.
\end{equation}

This pressure formulation reflects the ratio between predicted workload and effective shard processing ability. It is therefore more informative for smart-contract-centric workloads than transaction count alone, while still remaining lightweight enough for epoch-level online reconfiguration.

### Migration-Budgeted Optimization Objective

The reconfiguration objective is to jointly reduce shard-pressure imbalance and cross-shard interaction cost. To capture the first aspect, define the shard-pressure variance as
\begin{equation}
F_{\mathrm{load}}(X^t)
=
\frac{1}{K}\sum_{i=1}^{K}(P_i^t-\bar P^t)^2.
\end{equation}

This term penalizes execution-side skew across shards. Compared with a direct max-pressure objective, the variance form is smoother and more suitable for local differential evaluation during online migration.

To quantify the cost of cross-shard communication in a form directly tied to the binary assignment matrix, the weighted cross-shard cut cost is
\begin{equation}
F_{\mathrm{cross}}(X^t)
=
\sum_{(u,v)\in E^t}
e_{u,v}^t
\left(
1-\sum_{i=1}^{K}x_{u,i}^t x_{v,i}^t
\right).
\end{equation}

Because each account is assigned to exactly one shard, the term $1-\sum_{i=1}^{K}x_{u,i}^t x_{v,i}^t$ is $0$ when $u$ and $v$ are placed on the same shard and $1$ otherwise. Let
\begin{equation}
W_{\mathrm{total}}^t
=
\sum_{(u,v)\in E^t} e_{u,v}^t
\end{equation}
denote the total edge weight of the interaction graph. The normalized cross-shard cost is then
\begin{equation}
\begin{aligned}
\widetilde F_{\mathrm{cross}}(X^t)
&=
\frac{F_{\mathrm{cross}}(X^t)}
{W_{\mathrm{total}}^t+\varepsilon}.
\end{aligned}
\end{equation}

The normalization keeps the cut term comparable across epochs with different graph sizes and total interaction mass.

The joint objective function is
\begin{equation}
J(X^t)
=
\lambda F_{\mathrm{load}}(X^t)
+
(1-\lambda)\widetilde F_{\mathrm{cross}}(X^t),
\qquad
\lambda\in[0,1].
\end{equation}

The parameter $\lambda$ determines the tradeoff between pressure balancing and interaction preservation.

The optimization is subject to the following constraints:
\begin{equation}
\sum_{i=1}^{K}x_{j,i}^t=1,
\qquad
\forall j\in V^t,
\end{equation}
\begin{equation}
x_{j,i}^t\in\{0,1\},
\qquad
\forall j\in V^t,\ \forall i\in\{1,\dots,K\},
\end{equation}
\begin{equation}
\sum_{j\in V^t}\sum_{i=1}^{K}
\left|x_{j,i}^t-x_{j,i}^{t-1}\right|
\le 2B_{\max}.
\end{equation}

The first constraint enforces one-account-one-shard assignment, the second preserves binary decision variables, and the third limits how many accounts may be migrated at one reconfiguration boundary. Because each migrated account changes exactly two entries in its one-hot assignment row, the last inequality is equivalent to bounding the number of migrated accounts by $B_{\max}$.

The complete optimization problem is written explicitly as
\begin{equation}
\begin{aligned}
\min_{X^t}\quad
& J(X^t) \\
\text{s.t.}\quad
& \sum_{i=1}^{K}x_{j,i}^t=1,
&& \forall j\in V^t, \\
& x_{j,i}^t\in\{0,1\},
&& \forall j\in V^t, \\
& && \forall i\in\{1,\dots,K\}, \\
& \sum_{j\in V^t}\sum_{i=1}^{K}
\left|x_{j,i}^t-x_{j,i}^{t-1}\right| \\
& \le 2B_{\max}.
\end{aligned}
\end{equation}

Because the objective combines discrete assignment variables with a quadratic load term and a graph-cut term, the resulting problem is a constrained 0-1 quadratic program and is difficult to solve exactly at epoch boundaries.

## Priority-Queue-Based Heuristic Migration



### Migration Benefit and Local Differential Cost

To solve the above optimization problem efficiently, a heuristic account-migration algorithm is adopted instead of attempting exact optimization. Let $N(j)$ denote the graph neighborhood of $j$ in $G^t$. The algorithm first identifies overloaded shards with a tolerance parameter $\delta>0$:
\begin{equation}
H^t
=
\left\{
i\in\{1,\dots,K\}\mid P_i^t>(1+\delta)\bar P^t
\right\},
\end{equation}
and defines the admissible destination set as
\begin{equation}
L^t
=
\left\{
i\in\{1,\dots,K\}\mid P_i^t\le (1+\delta)\bar P^t
\right\}.
\end{equation}

For any shard $i$, define the interaction strength between account $j$ and shard $i$ as
\begin{equation}
E(j,i)
=
\sum_{k\in N(j),\ S^t(k)=i} e_{j,k}^t.
\end{equation}

For a candidate account $j$ currently placed on an overloaded shard $i_h=S^t(j)\in H^t$ and a destination shard $i_l\in L^t$, the heuristic migration score is defined as
\begin{equation}
\begin{aligned}
\mathrm{Score}(j,i_h\rightarrow i_l)
&=
\theta\cdot\frac{w_j^t}{c_{i_h}^t+\varepsilon} \\
&\quad+
(1-\theta)\cdot
\frac{E(j,i_l)-E(j,i_h)}{W_{\mathrm{total}}^t+\varepsilon}.
\end{aligned}
\end{equation}
where $\theta\in[0,1]$ and $W_{\mathrm{total}}^t$ is given above. The first term measures the expected pressure-relief benefit on the overloaded source shard, whereas the second term measures the expected locality gain. Separating $\theta$ from the objective weight $\lambda$ avoids conflating heuristic ranking with the final optimization target.

For each candidate account $j$, let $i_h=S^t(j)$ denote its current shard. The best admissible destination is
\begin{equation}
i_l^*(j)
=
\arg\max_{i\in L^t}\mathrm{Score}(j,i_h\rightarrow i).
\end{equation}

The score is used only for ranking. Before committing a migration, the algorithm evaluates the actual local objective change:
\begin{equation}
\Delta J
=
\lambda \Delta F_{\mathrm{load}}
+
(1-\lambda)\Delta \widetilde F_{\mathrm{cross}}.
\end{equation}

Suppose account $j$ moves from $i_h$ to $i_l$. Then only the source-shard and destination-shard loads change:
\begin{equation}
L_{i_h}^{t\prime}=L_{i_h}^t-w_j^t,
\qquad
L_{i_l}^{t\prime}=L_{i_l}^t+w_j^t.
\end{equation}

This implies
\begin{equation}
P_{i_h}^{t\prime}
=
P_{i_h}^t-\frac{w_j^t}{c_{i_h}^t+\varepsilon},
\qquad
P_{i_l}^{t\prime}
=
P_{i_l}^t+\frac{w_j^t}{c_{i_l}^t+\varepsilon},
\end{equation}
and
\begin{equation}
\bar P^{t\prime}
=
\bar P^t
+
\frac{1}{K}
\left(
\frac{w_j^t}{c_{i_l}^t+\varepsilon}
-
\frac{w_j^t}{c_{i_h}^t+\varepsilon}
\right).
\end{equation}

Using the definition of $F_{\mathrm{load}}(X^t)$, the load-term change can be computed locally as
\begin{equation}
\begin{aligned}
\Delta F_{\mathrm{load}}
&=
\frac{1}{K}\Big[
(P_{i_h}^{t\prime}-\bar P^{t\prime})^2 \\
&\qquad+
(P_{i_l}^{t\prime}-\bar P^{t\prime})^2 \\
&\qquad-
(P_{i_h}^{t}-\bar P^{t})^2
-
(P_{i_l}^{t}-\bar P^{t})^2
\Big].
\end{aligned}
\end{equation}

For the cut term, only edges incident to $j$ can change their contribution. Therefore,
\begin{equation}
\begin{aligned}
\Delta F_{\mathrm{cross}}
&=
\sum_{k\in N(j),\ S^t(k)=i_h} e_{j,k}^t \\
&\quad-
\sum_{k\in N(j),\ S^t(k)=i_l} e_{j,k}^t \\
&=
E(j,i_h)-E(j,i_l).
\end{aligned}
\end{equation}
which gives
\begin{equation}
\Delta \widetilde F_{\mathrm{cross}}
=
\frac{\Delta F_{\mathrm{cross}}}{W_{\mathrm{total}}^t+\varepsilon}.
\end{equation}

A candidate move is accepted only when
\begin{equation}
\Delta J<0.
\end{equation}

Thus, the score is used for efficient candidate ranking, whereas the final acceptance decision is governed by strict local decrease of the actual objective. This preserves a monotonic local-improvement direction even though the overall search remains heuristic.

### Priority-Queue Migration Procedure

The algorithm uses a max-heap to maintain candidate accounts ordered by migration benefit. Its execution at each epoch boundary can be summarized as follows.

\begin{enumerate}
\item Compute the predicted account loads $w_j^t$, shard capacities $c_i^t$, shard pressures $P_i^t$, and then identify the overloaded set $H^t$ and admissible set $L^t$.
\item For each account on shards in $H^t$, enumerate admissible destinations in $L^t$, compute the best destination by the above score, and insert the resulting candidate move into the max-heap.
\item Repeatedly extract the candidate with the largest score, evaluate its local objective change, and accept the migration only when it satisfies $\Delta J<0$ and the migration budget has not been exhausted.
\item After each accepted migration, update the shard loads, shard pressures, local cut contributions, and the heap keys of affected neighboring candidates, and then continue the search with the refreshed local state.
\end{enumerate}

Because the budget constraint bounds the total number of changed one-hot assignment entries by $2B_{\max}$, it is equivalent to allowing at most $B_{\max}$ account migrations at one reconfiguration boundary. This local-update strategy avoids a full scan of all accounts after every move and confines recomputation to the neighborhoods that actually changed. The procedure stops when the migration budget is exhausted, when the heap becomes empty, when no remaining candidate yields $\Delta J<0$, or when $H^t=\emptyset$.

### Complexity Analysis

Let $N$ be the number of active accounts, let $\bar d$ be the average degree of the interaction graph, and let $M\le B_{\max}$ be the number of accepted migrations. Constructing the candidate set and initializing the heap requires local interaction scans over candidate neighborhoods and therefore costs $O(N\bar d)$ in the worst case. Each accepted migration changes only the source shard, the destination shard, and the neighborhood of the migrated account. The local cut-difference computation is $O(\bar d)$, while refreshing affected candidate scores and maintaining the heap costs $O(\bar d\log N)$. Therefore, the total time complexity is
\begin{equation}
O(N\bar d + M\bar d \log N).
\end{equation}

This complexity is compatible with epoch-level online reconfiguration because recomputation is confined to affected local neighborhoods rather than the full graph after every accepted move.

## Experimental Evaluation



### Experimental Setup

The evaluation is conducted in the open-source sharding emulator BlockEmulator with PBFT as the intra-shard consensus protocol. All test nodes are deployed on a single physical machine equipped with an Intel Core i5-14600KF processor, 32\,GB memory, and Ubuntu 20.04 LTS. To emulate a wide-area network environment, the per-node bandwidth is limited to 20\,Mbps, the block interval is set to 3\,s, the block capacity is fixed at 2,000 transactions, and the reconfiguration gap is set to 100 consensus rounds.

To reflect realistic digital-asset workloads, 500,000 transactions are extracted from Ethereum Mainnet traces spanning block heights 0 to 999,999. Unless otherwise stated, the default injection rate is 2,000\,tx/s. The proposed method is compared against representative sharding baselines, including ContribChain~\cite{huang2025contribchain}, LB-Chain~\cite{li2023lb}, BrokerChain~\cite{huang2022brokerchain}, Presto~\cite{ding2024presto}, and CLPA. The load-distribution and shard-time comparisons are reported against ContribChain and LB-Chain, the throughput sweeps are reported against ContribChain, BrokerChain, and CLPA, and the mempool analysis is reported against ContribChain and Presto, consistent with the stored plots for each metric. All reported comparisons use the same emulator configuration and workload trace so that the observed differences reflect the effect of the balancing mechanism rather than different runtime settings. LB-Chain is the closest account-migration baseline, whereas BrokerChain and Presto primarily contextualize cross-shard coordination behavior and ContribChain contextualizes stress-aware sharding. The comparisons should therefore be read as controlled end-to-end system comparisons in one common environment rather than as a claim that all baselines solve exactly the same optimization problem.

The current evaluation should therefore be read as a trace-driven comparison under one controlled runtime configuration rather than as a multi-run robustness study.
The evaluation focuses on shard-load distribution, shard processing time, system throughput, and mempool backlog under different resource and concurrency settings.

### Load Balancing Behavior

Fig.~1 shows the evolution of shard-load distributions over five consecutive reconfiguration epochs. The heatmap should be read as evidence that the method reduces execution-side skew rather than merely redistributing transaction counts. Several baseline methods still exhibit obvious local overload in the early rounds, and some shards exceed a load ratio of 2.0, which is consistent with balancing criteria that do not fully distinguish cheap interactions from gas-intensive contract execution. By contrast, the proposed method keeps the maximum load ratio around 1.4 and gradually narrows the shard-load range to approximately 0.86--1.10 after reconfiguration. The result indicates not only a lower peak pressure, but also a faster convergence toward a more even shard-level operating regime before straggler shards can dominate later rounds.

\begin{center}
    \includegraphics[width=0.95\linewidth]{src/resources/heatmap.png}
    \captionof{figure}{Heatmap comparison of shard-load distribution over five consecutive epochs}
\end{center}

The shard-processing-time comparison leads to a similar conclusion. As shown in Fig.~2, ContribChain exhibits a clear straggler-shard effect, with several shards exceeding 1,300\,s of processing time, while LB-Chain reduces the dispersion and brings most shards close to 700\,s. The proposed method keeps all shard processing times below about 600\,s and yields the tightest distribution among the compared schemes. Since end-to-end throughput in a sharded system is bounded by its slowest shard rather than its average shard, this reduction in the long tail of processing time is a practically meaningful sign that the balancing policy is removing real bottlenecks rather than only improving a nominal load metric.

\begin{center}
    \includegraphics[width=0.90\linewidth]{src/resources/fig_straggler_shards.png}
    \captionof{figure}{Comparison of actual shard processing time under different methods}
\end{center}

### Throughput Under Different Resources

Fig.~3 reports the impact of bandwidth on system throughput. As the available bandwidth increases from 1\,Mbps to 20\,Mbps, all methods improve and then gradually saturate. In the low-bandwidth regime, the proposed method consistently outperforms the main compared baselines, indicating that preserving interaction locality can reduce the coordination cost that otherwise dominates under limited network resources. Near 20\,Mbps, the proposed method reaches about 1,800 TPS.

\begin{center}
    \includegraphics[width=0.95\linewidth]{src/resources/fig_bandwidth.png}
    \captionof{figure}{Effect of bandwidth limitation on system throughput}
\end{center}

Fig.~4 shows the throughput trend under different transaction injection rates. All methods improve as the load rises in the low-to-medium range, but the baselines begin to saturate when the injection rate reaches 2,500--3,000 TPS. Their throughput typically stabilizes around 1,300--1,400 TPS, indicating persistent backlog accumulation. In contrast, the proposed method still maintains more than 1,800 TPS. This behavior is consistent with the intended role of gas-aware pressure estimation: once workload intensity increases, execution-cost heterogeneity becomes harder to ignore, and a transaction-count proxy alone becomes less reliable for avoiding shard-level bottlenecks.

\begin{center}
    \includegraphics[width=0.95\linewidth]{src/resources/fig_injection_rates.png}
    \captionof{figure}{Effect of transaction injection rate on system throughput}
\end{center}

The shard-count sweep in Fig.~5 further demonstrates the scalability benefit of the proposed approach. Although all methods improve as the number of shards increases, the gain of the baselines slows down when cross-shard traffic becomes more frequent. The proposed method preserves strong account interactions within the same shard while keeping load variance under control, and thus reaches about 3,800 TPS at 32 shards. In the same setting, the compared baselines saturate near 2,900 TPS. The result suggests that the method helps additional shards translate into usable parallelism instead of having much of the expansion gain offset by rising coordination overhead.

\begin{center}
    \includegraphics[width=0.95\linewidth]{src/resources/fig_shard_numbers.png}
    \captionof{figure}{Effect of shard number on system throughput}
\end{center}

### Mempool Backlog Evolution

The mempool queue results further confirm the benefit of the proposed design. At 1,500 TPS, the queue grows during the injection phase and then shrinks after injection stops. The proposed method reaches a lower peak backlog and clears the queue faster than the baselines. More specifically, its peak queue length is about $0.9 \times 10^{4}$ transactions, compared with approximately $1.45 \times 10^{4}$ for ContribChain and $1.25 \times 10^{4}$ for Presto. The smaller backlog indicates that the gain is visible not only in average throughput, but also in the system's ability to absorb transient pressure before congestion becomes persistent.

\begin{center}
    \includegraphics[width=0.95\linewidth]{src/resources/fig_queue_1500.png}
    \captionof{figure}{Queue-length evolution under an injection rate of 1,500 TPS}
\end{center}

At 2,500 TPS, backlog accumulation becomes more severe for all methods, but the proposed method still maintains a smaller peak queue and faster drainage. As shown in Fig.~7, the peak backlog of the proposed method is about $2.9 \times 10^{4}$ transactions, while ContribChain reaches around $5.0 \times 10^{4}$. This corresponds to a reduction of about 42.00\% in peak backlog. Under this heavier workload, the queueing behavior reinforces the central claim of the paper: balancing decisions become more robust when execution overhead and interaction topology are modeled jointly rather than separately.

\begin{center}
    \includegraphics[width=0.95\linewidth]{src/resources/fig_queue_2500.png}
    \captionof{figure}{Queue-length evolution under an injection rate of 2,500 TPS}
\end{center}

## Discussion

The experimental results support the central design claim of the paper: shard reconfiguration should be guided by both execution pressure and interaction structure rather than by transaction counts alone. The heatmap and shard-processing-time comparisons show that the main gain is not merely a cosmetic redistribution of activity, but a reduction in execution-side skew. Once gas-aware pressure estimation is introduced, expensive contracts and high-cost interaction clusters are less likely to accumulate in a few shards, which in turn suppresses the straggler effect. This matters because system throughput in a sharded blockchain is often bounded by the slowest shard rather than by average shard behavior.

The throughput results clarify where this modeling choice becomes most valuable. Under limited bandwidth, preserving interaction locality reduces the frequency of cross-shard coordination and helps the system use scarce network resources more effectively. Under high injection rates, the pressure model becomes more important because execution-cost heterogeneity can no longer be hidden behind similar transaction counts. Under larger shard counts, the method continues to help because the probability of splitting interaction-heavy account groups increases with the number of partitions. Taken together, these observations suggest that the reported performance gains come from addressing the two main sources of loss in sharded systems simultaneously: uneven execution pressure and rising cross-shard overhead.

At the same time, the scope of the current evidence should be stated conservatively. First, the method relies on the quality of the sliding interaction window and EMA-based estimation, so it may respond slowly to abrupt workload shifts. Second, the migration procedure is heuristic and greedy, which makes it practical for epoch-level execution but does not provide a global optimum for the underlying constrained quadratic program. Third, the evaluation remains a trace-driven study under one BlockEmulator configuration and one reported set of parameter choices, rather than a full sensitivity or multi-platform robustness analysis. Fourth, the present evaluation emphasizes performance outcomes and does not separately quantify migration-state volume, reconfiguration latency, or migration-induced communication cost. The present results therefore support the effectiveness of the method in this evaluated setting, but they should not be interpreted as a complete characterization of every deployment environment.

The system-level scope also deserves clarification. The method assumes that migrations are executed at epoch boundaries after the confirmed transactions in the current accounting window have been observed. State-transfer correctness, epoch-boundary consistency, and the underlying PBFT execution semantics are inherited from the sharded blockchain protocol and the BlockEmulator environment rather than redesigned by this paper. In that sense, the contribution here is a reconfiguration policy rather than a new safety protocol. The EMA smoothing and migration-budget constraint help reduce unnecessary churn, but they do not eliminate the possibility of oscillatory migrations under rapidly shifting or adversarial workloads, which remains an important direction for future refinement.

These limitations also indicate several natural next steps. More adaptive prediction mechanisms may improve responsiveness to sudden workload changes, and broader distributed experiments could clarify how the same migration policy behaves under different consensus, network, and deployment conditions. Even with these caveats, the current study already supports a practical takeaway: epoch-level reconfiguration for smart-contract-oriented sharded blockchains becomes more reliable when execution overhead and interaction topology are modeled together instead of being optimized separately.

## Conclusions

This paper studies shard reconfiguration for smart-contract-oriented blockchains from the perspective of joint load balancing and interaction preservation. The proposed method models active accounts as a temporal interaction graph, uses gas-aware edge weights and EMA-based pressure estimation to describe shard stress more faithfully, and formulates account placement as a migration-budgeted optimization problem over load variance and cross-shard cut cost. To solve the resulting constrained assignment problem in a practical way, the paper develops a priority-queue heuristic with local differential updates for efficient epoch-level account migration.

Experiments on Ethereum Mainnet traces in BlockEmulator show that this design leads to more balanced shard pressure, shorter shard processing time, higher throughput under multiple bandwidth, workload, and shard-count settings, and lower mempool backlog at high injection rates. Within the scope of the evaluated trace-driven setting, the results support a clear conclusion: shard reconfiguration becomes more effective when execution overhead and interaction topology are modeled together, rather than when either is treated in isolation.

\vspace{2mm}
