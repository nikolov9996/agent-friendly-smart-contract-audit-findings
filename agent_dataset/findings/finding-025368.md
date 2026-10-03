---
id: 25368
severity: "Low/Info"
---

# SyrupRouter::depositWithPermit() may be DoSed by frontrunning ERC20::permit()

## Description

[SyrupRouter::depositWithPermit()](<https://github.com/maple-labs/syrup-router/blob/main/contracts/SyrupRouter.sol#L39>) uses the permit functionality of the asset by [calling](<https://github.com/maple-labs/syrup-router/blob/main/contracts/SyrupRouter.sol#L47>) IERC20Like(asset).permit(owner_, address([this](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/cryptography/EIP712.sol#L88-L90>)), amount_, deadline_, v_, r_, s_);.

Some griefer may spot the SyrupRouter::depositWithPermit() transaction, frontrun it and call the IERC20Like::permit() function directly, spending the nonce of the signature and DoSing the router.

## Proof of Concept

No PoC provided.

## Recommendation

An attacker has no profit from executing so it [is](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/cryptography/EIP712.sol#L37-L38>) not expected to happen, but some measures could still be taken.

Some [examples](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/extensions/ERC20Permit.sol>) are:

1. Get the allowance and only call IERC20Like::permit() if it [is](<https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/cryptography/MessageHashUtils.sol#L76>) smaller than amount_.
2. Use try/catch.
3. Flashbots.
