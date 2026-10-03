---
id: 25031
severity: "Medium"
---

# Unhandled request invalidation by the owner of Etherfi will lead to stuck debt

## Description



## Proof of Concept

`WithdrawRequestNFT::claimWithdraw()` from Etherfi [checks](<https://github.com/etherfi-protocol/smart-contracts/blob/master/src/WithdrawRequestNFT.sol#L94>) that the request is valid. The owner of `WithdrawRequestNFT` may [invalidate](<https://github.com/etherfi-protocol/smart-contracts/blob/master/src/WithdrawRequestNFT.sol#L174>) the request at any time and claim it for [itself](<https://github.com/etherfi-protocol/smart-contracts/blob/master/src/WithdrawRequestNFT.sol#L135>).

Thus, as withdrawals in `YieldEthStakingEtherfi` can not be canceled and there is no way to handle invalidated withdrawals, the debt from the nft will never be repaid if the owner claims the nft for itself. If the owner validates the request later, there will still be a period of unknown duration during which it's not possible to repay the debt.

## Recommendation

Create a mechanism to handle invalidated withdrawals or withdrawals that have been claimed by the owner.
