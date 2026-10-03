---
id: 25338
severity: "Crit/High"
---

# Pool Delegates can set a really high origination fee and steal all pool funds.

## Description

The delegate origination fee can be set to any value at any time and anyone can deploy a loan, so the delegate can receive all the funds of a loan. Exploit scenario

- gather funds to a pool with a regular origination fee
- given enough funds, increase the origination fee to the pool amount minus the platformOriginationFee (which can be close to zero if the delegate creates the loan with 1 payment interval and 1 number of payments)
- create a fake loan ([anyone can deploy a loan](<https://github.com/maple-labs/three-sigma-audit-2023-04-10/issues/28>)) and fund it

## Proof of Concept

No PoC provided.

## Recommendation

The following mitigation options were proposed:

```solidity
- Redeploy factory and fix anyone can deploy a loan;
- Set an origination fee limit;
- Don't allow changing the origination fee;
- Set a timelock/minimum withdrawal cycles to change the origination fee;
```

- Require governor approval on fee change.
