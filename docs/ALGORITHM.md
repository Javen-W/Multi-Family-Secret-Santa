# Assignment algorithm

A program starts from a participant set $P$. Each person $i \in P$ may declare exclusion tokens. After cleaning, those tokens expand to a set of other people $E(i) \subseteq P \setminus \{i\}$. A token may name a person, a group, or both. Group membership itself does not add exclusions.

## Forbidden pairs

Exclusions block both directions, even when only one person listed the other. The forbidden relation is

$$
F = \{ (a, b) \in P \times P \mid a \neq b,\ b \in E(a)\ \text{or}\ a \in E(b) \}.
$$

Self-pairs are also forbidden. The allowed directed graph $G$ therefore has an edge $a \rightarrow b$ only when

$$
a \neq b \quad \text{and} \quad (a, b) \notin F.
$$

Because $F$ is symmetric, $a \rightarrow b$ exists exactly when $b \rightarrow a$ exists.

## What counts as a solution

Let $P' \subseteq P$ be the participants who remain after pruning. A solution is a permutation $\pi: P' \to P'$ such that

$$
\pi(i) \neq i
\quad \text{and} \quad
(i, \pi(i)) \notin F
\quad \text{for every } i \in P'.
$$

Equivalently, $\pi$ is a perfect matching in the bipartite graph with a giver copy and a recipient copy of each person in $P'$, using only edges from $G$. A permutation may contain mutual pairs, longer cycles, or both. The exchange does not require the gift to be returned.

## Removing infeasible individuals

Someone who cannot give a legal gift, or cannot receive one, cannot appear in any permutation. While such a person exists, that person is removed and the reason is logged:

- out-degree $0$ and in-degree $0$: no legal giver or recipient
- out-degree $0$: no legal recipient
- in-degree $0$: no legal giver

Removal only deletes edges, so the scan repeats until every remaining person has in-degree and out-degree at least $1$. This catches people who excluded everybody else, and people who become impossible only after a neighbor was removed. Because $F$ is symmetric, in-degree equals out-degree, and a removed participant has neither a legal giver nor a legal recipient.

If fewer than two people remain, or the remaining graph has no perfect matching, the program raises `InfeasibleProgramError` and sends no email. Participants who still have legal edges but cannot all be covered together are not dropped one by one. Dropping them would silently change who is in the exchange.

## Search

The matching step is depth-first augmenting-path search. Giver order and each adjacency list are shuffled with `random.Random`. The shuffle changes which valid permutation is returned. It does not change whether a perfect matching exists: the search finds one whenever the pruned graph has one.

When `seed` is set in the config, the same registry produces the same assignment. When `seed` is `null`, each run draws a new shuffle.

## Checks recorded in the log

Before email, the solver records three checks over the assignment it produced:

$$
\begin{aligned}
\{\pi(i) \mid i \in P'\} &= P' \\
\pi(i) &\neq i \\
(i, \pi(i)) &\notin F
\end{aligned}
$$

The organizer log prints each check as `ok` or `failed`, along with ignored tokens, removed names, and every pair $i \rightarrow \pi(i)$.
