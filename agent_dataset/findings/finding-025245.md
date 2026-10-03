---
id: 25245
severity: "Low/Info"
---

# Strategies in the ReservePool could be implemented as an array and Strategy packed

## Description

The strategies are stored in the ReservePool as a mapping _strategies and length _strategyCount. This could be reduced to an array of [Strategy](<https://github.com/JackFrostDev/glacier-contracts/blob/main/contracts/protocol/ReservePool/GReservePool.sol#L36-L44>), Strategy[] public _strategies;, increasing readability and gas savings.

Additionally, the struct Strategy can be reduced to 2 variables and occupy only 1 storage slot by packing the logic and the weight together (deposited is not needed).

## Proof of Concept

No PoC provided.

## Recommendation

Refactor the code to:

```solidity
contract GReservePool is Initializable, IGReservePool, AccessControlManager
{
    ... struct Strategy {
```

IGReserveStrategy logic; // 20 bytes uint96 weight; // so weight can have at most 12 bytes or uint96 to fill the 32 bytes storage slot

```solidity
}
Strategy[] public _strategies;
... }
```
