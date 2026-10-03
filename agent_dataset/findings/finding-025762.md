---
id: 25762
severity: "Medium"
---

# Time-sensitive contracts deployed on zkSync

## Description



## Proof of Concept

Many contracts use `block.number` to measure the time as the miners were able to manipulate the `timestamp` (the `timestamp` could be easily gamed over short intervals). So, it was assumed that `block.number` is a safer and more accurate source of measuring time than `timestamp`.

For instance, if a defi project sets 144000 block interval to release the interest, it means approximately `144000 * 12 = 20 days`. Please note that each block in Ethereum takes almost 12 second.

If the same defi project is deployed on zkSync, it will not operate as expected. Because there is no time-bound for the blocks in zkSync (the interval may be 30 seconds or 1 week). So, the time to release the interest can be between 50 days to 2762 days.

Since, it is assumed that zkSync is Ethereum compatible, any deployed contracts on Ethereum may deploy their contract in zkSync without noting such big difference.

Even if the contracts use `timestamp` to measure the time, there will be another issue. In the contract `SystemContext.sol`, it is possible to set new block with the same `timestamp` as previous block, but with incremented block number. [https://github.com/code-423n4/2023-03-zksync/blob/21d9a364a4a75adfa6f1e038232d8c0f39858a64/contracts/SystemContext.sol#L116](<https://github.com/code-423n4/2023-03-zksync/blob/21d9a364a4a75adfa6f1e038232d8c0f39858a64/contracts/SystemContext.sol#L116>)

In other words, new blocks are created but their time is frozen. Please note that freezing time can not be lasted for a long time, because when committing block their `timestamp` will be validated against a defined boundary.

## Recommendation

It should be explicitly mentioned that block intervals in zkSync are not compatible with Ethereum. So, time-sensitive contracts will be noted.

Moreover, the equal sign should be removed in the following line: [https://github.com/code-423n4/2023-03-zksync/blob/21d9a364a4a75adfa6f1e038232d8c0f39858a64/contracts/SystemContext.sol#L116](<https://github.com/code-423n4/2023-03-zksync/blob/21d9a364a4a75adfa6f1e038232d8c0f39858a64/contracts/SystemContext.sol#L116>)
