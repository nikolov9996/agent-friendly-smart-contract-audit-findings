---
id: 2802
severity: "High"
---

# Potential issues that can arise from BGT being reward token

## Description

The expected reward token gotten from staking on berachain is potentially the Bera Governance Token, BGT.
```solidity
/// @notice ERC20 token in which rewards are denominated and distributed.
/// Typically the BGT(i.e. Berachain Governance Token)
function REWARD_TOKEN() external view returns (IERC20);
```
BGT, by design, is not transferrable, except by specified senders. From the docs.
$BGT is non-transferrable and can only be acquired by providing liquidity in PoL-eligible assets (e.g. liquidity on Bex).
And as can be seen from the token contract, (albeit testnet), the tokens can only be transferred by approved senders. Important to note that users only need to be approved to send the tokens, anyone can receive the token.
```solidity
function transfer(
    address to,
    uint256 amount
) public override(IERC20, ERC20Upgradeable) onlyApprovedSender(msg.sender) checkUnboostedBalance(msg.sender, amount) returns (bool) {
    return super.transfer(to, amount);
}
```
Assuming staking is enabled, during deposits, withdrawals and rebalancing, the _preAction function is called. The function unstakes from berachain vault and attempts to send to the fee recipient.
```solidity
for (uint256 i = 0; i < rewardsVaults.length; i++) {
    IBerachainRewardsVault rewardsVault = rewardsVaults[i];
    if (address(rewardsVault) != NULL_ADDRESS) {
        _unstakeAndClaimRewards(rewardsVault); //@note
        // _transferRewardsToFarmingContract //(self, rewardsVault); //@note
    }
}
```
Here, two issues are likely to arise:
The functions that attempt to claim rewards will all fail as although, aegis vault will be able to receive the tokens from BerachainRewardsVaults, it will not be able to transfer it to the farming contract due to not being an approved sender. This is potentially all of the major protocol operations that depend on _preAction function, the collectRewards function and setStakingStatus function.
The claimed rewards may be stuck in the farming contract if it's not made a whitelisted sender.

## Proof of Concept

No poc.

## Recommendation

Dealing with this is a bit tricky since it is external admin-dependent. I'd recommend introducing queries for whitelisted status before the tokens are transferred and the farming contract is set. If the contracts are not whitelisted, skip the transfers instead.
For example:
When setting the farming contract, we can insist that only whitelisted farming contracts can be set.
```solidity
function setFarmingContract(address _farmingContract) external override {
    _onlyAdmin();
    IERC20 rewardToken = rewardsVault.REWARD_TOKEN();
    require(rewardToken.isWhitelistedSender(_farmingContract), "Not whitelisted");
    if (berachainState.farmingContract != _farmingContract) {
        berachainState.farmingContract = _farmingContract;
        emit FarmingContract(msg.sender, _farmingContract);
    }
}
```
When handling rewards transfers in preAction and collectRewards, we can skip sending rewards if the vault itself is not whitelisted.
```solidity
function _transferRewardsToFarmingContract(
    BerachainState memory self,
    IBerachainRewardsVault rewardsVault
) private {
    if (self.farmingContract != NULL_ADDRESS) {
        IERC20 rewardToken = rewardsVault.REWARD_TOKEN();
        uint256 rewardBalance = rewardToken.balanceOf(address(this));
        if (rewardBalance > 0 && rewardToken.isWhitelistedSender(address(this))) {
            rewardToken.safeTransfer(self.farmingContract, rewardBalance);
        }
    }
}
```
Overall, the fix depends on the protocol's plans for the tokens, but the token's intrinsic property should be taken into consideration.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability stems from the fact that the reward token used by the staking system is the Berachain Governance Token (BGT), which is deliberately designed as a non‑transferable ERC20. The token contract restricts the transfer function with an onlyApprovedSender modifier, meaning that only addresses that have been explicitly added to a whitelist can invoke transfer. The staking contract and its associated farming contract are not included in this whitelist. During normal operation the _preAction routine, collectRewards and setStakingStatus attempt to unstake BGT from a BerachainRewardsVault and then forward the claimed amount to the farming contract. Because the staking contract is not an approved sender, the call to BGT.transfer reverts, causing the claim transaction to fail or, if the failure is ignored, leaving the reward balance locked inside the vault or the staking contract. From a user perspective the expected outcome – a visible increase in their reward balance or a successful receipt of a refund – does not occur; users may see their balance remain unchanged or even appear to be reduced after a withdrawal, leading to confusion that funds disappeared. The issue is discovered during a security review that inspected the token’s transfer restrictions and traced the reward flow logic. It is hard to notice because the contract does not emit a specific error about whitelist failure and the UI may simply show a successful transaction hash while the reward amount is never credited. The impact is high: reward distribution is broken, accounting entries for earned BGT are missing, and the protocol cannot honor its incentive model, potentially eroding trust and causing loss of economic value for stakers. The bug belongs to the class of non‑transferable token misuse or whitelist‑restricted token transfer errors, where a contract assumes a token behaves like a standard ERC20 but the token enforces additional sender restrictions. The fix requires either adding the staking and farming contracts to the token’s approved‑sender list, or redesigning the reward handling code to check the whitelist status before attempting a transfer and to skip or revert the operation when the contract is not authorized. In practice this means introducing a require(isWhitelistedSender(address(this))) guard around reward transfers or restricting the setFarmingContract function to only accept contracts that are already whitelisted, thereby aligning the protocol’s business logic with the token’s transfer constraints.
