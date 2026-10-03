---
id: 25352
severity: "Low/Info"
---

# The DaiJoin contract may be caged which will DoS withdrawals forever

## Description

The [daiJoin](<https://vscode.blockscan.com/ethereum/0x9759A6Ac90977b93B58547b4A71c78317f391A28>) contract may be caged, which means exit() is DoSed forever.

This is called in the [psmWrapper](<https://vscode.blockscan.com/ethereum/0xA188EEC8F81263234dA3622A406892F3D630f98c>) buyGem(), legacyDaiJoin.exit(address(this), usdsInWad);, so it would be forever DoSed as there is no way to 'uncage'.

## Proof of Concept

No PoC provided.

## Recommendation

It's possible to set a new Psm in the Sky strategy but it is something to keep in mind.
