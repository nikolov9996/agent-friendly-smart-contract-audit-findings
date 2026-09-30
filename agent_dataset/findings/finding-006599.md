---
id: 6599
severity: "High"
---

# RewardsController uses inconsistent scaling in handleAction and can lead to transfer DoS to/from minipool market

## Description

RewardController.handleAction has a special case to handle the case when user is a minipool market:
• RewardsController.sol#L134-L145:
```solidity
if (_isAtokenERC6909[user] == true) {
    (uint256 assetID,) = IAERC6909(user).getIdForUnderlying(IAToken(msg.sender).WRAPPER_ADDRESS());
    // For trancheATokens we calculate the total supply of the AERC6909 ID for the assetID.
    // We subtract the current balance.
    uint256 totalSupplyAsset = IAERC6909(user).scaledTotalSupply(assetID); // <<<
    uint256 diff = totalSupplyAsset - userBalance;
    _totalDiff[msg.sender] = _totalDiff[msg.sender] - lastReportedDiff[msg.sender][user] + diff;
    lastReportedDiff[msg.sender][user] = diff;
    userBalance = totalSupplyAsset;
}
```
We can see that the function fetches scaledTotalSupply in order to compute the difference between the shares of MLP aToken which are due to the minipool and what is actually held by the minipool. These "shares" which are not accounted for in aToken.scaledTotalSupply should be rewarded, and thus this is why _totalDiff[msg.sender] is computed and then added to totalSupply for updating reward state:
• RewardsController.sol#L146-L148:
```solidity
_updateUserRewardsPerAssetInternal(
    msg.sender,
    user,
    userBalance,
    totalSupply + _totalDiff[msg.sender] // <<<
);
```
Unfortunately, it is inaccurate to use IAERC6909(user).scaledTotalSupply in this context, since the total supply is scaled according to the minipool market index, while all other amounts are only scaled according to main lending pool index. To showcase how it can lead to DOS of transfers from the ERC6909 market, we will use a simple example:
Scenario:
• Preconditions:
Params
Value
asset
aWETH
MLP liquidity index
minipool liquidity index
1.05
initial total supply
• Steps:
– Alice mints 100 aWETH by depositing in the main lending pool.
– Alice deposits the 100 aWETH into minipool, and is minted 95.2 shares of aWETH6909. After this step, aWETH6909.scaledTotalSupply is 95.2e18.
• Alice attempts to withdraw the 100 aWETH, but the following values are used in RewardController.handleAction during transfer:
– IncentivizedERC20.sol#L191-L199:
```solidity
if (address(_getIncentivesController()) != address(0)) {
    uint256 currentTotalSupply = _totalSupply;
    _getIncentivesController().handleAction(sender, currentTotalSupply, oldSenderBalance); // <<<
    if (sender != recipient) {
        _getIncentivesController().handleAction(
            recipient, currentTotalSupply, oldRecipientBalance
        );
    }
}
```
Params
Value
sender
aWETH6909
currentTotalSupply
100e18
oldSenderBalance
100e18
Which means handleAction will underflow (scaledTotalSupply == 95.2e18):
– RewardsController.sol#L134-L145:
```solidity
if (_isAtokenERC6909[user] == true) {
    (uint256 assetID,) = IAERC6909(user).getIdForUnderlying(IAToken(msg.sender).WRAPPER_ADDRESS());
    // For trancheATokens we calculate the total supply of the AERC6909 ID for the assetID.
    // We subtract the current balance.
    uint256 totalSupplyAsset = IAERC6909(user).scaledTotalSupply(assetID);
    uint256 diff = totalSupplyAsset - userBalance; // <<<
    _totalDiff[msg.sender] = _totalDiff[msg.sender] - lastReportedDiff[msg.sender][user] + diff;
    lastReportedDiff[msg.sender][user] = diff;
    userBalance = totalSupplyAsset;
}
```
Alice is unable to withdraw her funds.

## Proof of Concept

no poc

## Recommendation

We should use totalSupply to keep units consistent:
• RewardsController.sol#L134-L145:
```solidity
if (_isAtokenERC6909[user] == true) {
    (uint256 assetID,) = IAERC6909(user).getIdForUnderlying(IAToken(msg.sender).WRAPPER_ADDRESS());
    // For trancheATokens we calculate the total supply of the AERC6909 ID for the assetID.
    // We subtract the current balance.
    uint256 totalSupplyAsset = IAERC6909(user).totalSupply(assetID);
    uint256 diff = totalSupplyAsset - userBalance;
    _totalDiff[msg.sender] = _totalDiff[msg.sender] - lastReportedDiff[msg.sender][user] + diff;
    lastReportedDiff[msg.sender][user] = diff;
    userBalance = totalSupplyAsset;
}
```
Note that it may seem a bit counterintuitive, because this total supply includes shares of lending pool which are accrued as interest, and have never been "minted" yet.

## Derived Narrative

The following field is derived content and may not be source-grounded:

RewardsController.handleAction mixes two different scaling conventions when processing a minipool market (ERC6909 aToken). The function reads IAERC6909(user).scaledTotalSupply, which is expressed in units that incorporate the minipool liquidity index, but later combines this value with balances that are scaled only with the main lending pool index. Because the two indices diverge, the subtraction totalSupplyAsset - userBalance can underflow, causing the internal _totalDiff calculation to wrap and the subsequent _updateUserRewardsPerAssetInternal call to revert. In practice a user who deposits assets into the main pool, moves the resulting aTokens into a minipool, and then tries to withdraw will see the withdrawal transaction fail with no funds transferred, even though the UI shows the expected balance. The bug was discovered during a manual audit of the RewardsController logic, where the special‑case branch for ERC6909 tokens was examined and the mismatch of scaling functions was identified. The issue is subtle because the numbers involved are close and the underflow only appears when the minipool index is higher than the main pool index, a condition that is not obvious from the contract’s public interface. The vulnerability belongs to the class of accounting‑scale mismatches that break reward calculations and can lead to a denial‑of‑service on token transfers. Affected parties include any user of the minipool market, the protocol’s reward distribution mechanism, and potentially the overall liquidity of the platform. The recommended fix is to replace the call to scaledTotalSupply with totalSupply, which returns the raw supply without applying the minipool index, thereby keeping the units consistent across the reward calculation. After the change the diff computation will use comparable units, preventing the underflow and allowing withdrawals to succeed.
