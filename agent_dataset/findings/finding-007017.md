---
id: 7017
severity: "High"
---

# The USDT Reward Claiming Functionality of VestedStaking Can Be DoSed Due to a Logical Error

## Description

There is a logical error in the current implementation of the claimRewards function in the VestedStaking.sol contract, and more specifically, in its logic for claiming USDT rewards.
```solidity
if (claimUsdt) {
    if (usdtAmount != 0) {
        uint256 beforeBalance = IUSDT_TOKEN.balanceOf(address(this));
        IUSDT_TOKEN.safeTransfer(msg.sender , usdtAmount);
        usdtAmount = IUSDT_TOKEN.balanceOf(msg.sender) - beforeBalance;
    }
}
```
As it can be seen, the balance of the current contract is being fetched into the beforeBalance variable. After the transfer of USDT rewards to the msg.sender that value gets subtracted from the msg.sender balance, in order to determine the actual amount of USDT that was transferred. Those operations will lead to the wrong value of usdtAmount being calculated. Not only that but when the vester of the given contract has a zero or close to zero USDT balance, this issue can be abused by malicious users in order to DoS the USDT reward-claiming functionality of the vested staking contract. This can be achieved by directly transferring a USDT amount that is greater than the vester’s balance to the VestedStaking contract - leading to the USDT reward claiming functionality always reverting on VestedStaking.sol/L172 due to an arithmetic underflow error. The same DoS scenario is possible if the USDT transfer fees get enabled and they are greater than the vester’s USDT balance.

Users won’t be able to claim their USDT staking rewards from their VestedStaking contracts. Additionally, the Claim event at the end of the function will be emitted with a wrong USDT value when the function is not DoSed.

## Proof of Concept

The following test demonstrates how a user that has a X USDT balance can be prevented from claiming their USDT staking rewards.
```solidity
it("should revert reward claiming when the vester has a X USDT balance and the contract has a > X USDT balance", async () => {
    const vesterUsdtBalance = ethers.parseUnits("2", 6); // Vester has a total of 2 USDT
    await usdt.connect(deployer).transfer(vesterAddress , vesterUsdtBalance);
    const depositAmount = ethers.parseUnits("1000", 6);
    await usdt.connect(deployer).approve(stakedCSX.getAddress(),
    depositAmount);
    await stakedCSX
    .connect(deployer)
    .depositDividend(await usdt.getAddress(), depositAmount);
    await stakedCSX.connect(council).distribute(false, false, true);

    // Transfer 0.000001 USDT more than the vested balance to make the claimRewards() function revert
    await usdt
    .connect(deployer)
    .transfer(vestedStaking.getAddress(), vesterUsdtBalance + BigInt(1));
    await expect(
        vestedStaking.connect(vesterAddress).claimRewards(false, true, false,
        false)
    ).to.be.revertedWithPanic("0x11"); // Arithmetic under/overflow panic code
});
```
To run the PoC test, add it to the VestedStaking describe block of the VestedStaking.test.ts file and then run npx hardhat test --grep "should revert reward claiming when the vester has a X USDT balance and the contract has a > X USDT balance" in the project root directory

## Recommendation

Fetch the balance of msg.sender in the beforeBalance variable instead of the balance of the current contract:
```solidity
if (claimUsdt) {
    if (usdtAmount != 0) {
        - uint256 beforeBalance = IUSDT_TOKEN.balanceOf(address(this));
        + uint256 beforeBalance = IUSDT_TOKEN.balanceOf(msg.sender);
        IUSDT_TOKEN.safeTransfer(msg.sender , usdtAmount);
        usdtAmount = IUSDT_TOKEN.balanceOf(msg.sender) - beforeBalance;
    }
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the USDT reward‑claiming path of the VestedStaking contract. When a user calls claimRewards with claimUsdt set to true and a non‑zero usdtAmount, the function records the contract’s own USDT balance in a variable called beforeBalance, then transfers the requested amount to the caller and finally recomputes usdtAmount as the difference between the caller’s post‑transfer balance and the previously stored beforeBalance. Because beforeBalance was taken from the contract instead of the caller, the subtraction uses mismatched sources: it subtracts the contract’s balance from the caller’s balance. In normal situations where the contract holds enough USDT, the error may go unnoticed, but when the contract’s balance is zero or lower than the amount being transferred – for example after an attacker deliberately sends a tiny excess of USDT to the contract or when transfer fees are enabled and exceed the contract’s holdings – the subtraction underflows, triggering Solidity’s panic code 0x11 (arithmetic under/overflow). The transaction then reverts, effectively denying any user the ability to claim their USDT rewards. From the user’s perspective the claim either fails with a low‑level panic or succeeds but the emitted Claim event reports an incorrect USDT amount, often zero, while the user’s wallet shows no new tokens. The root cause is an accounting mistake: the code intended to measure the recipient’s balance before the transfer, but mistakenly measured the contract’s balance, breaking the invariant that the difference equals the transferred amount. This logical flaw was discovered during a security audit by Shiedify, which also provided a proof‑of‑concept test that forces the underflow by depositing a single wei‑scale USDT amount greater than the vester’s balance. The issue is hard to spot because the transfer itself appears successful and the bug only manifests under specific low‑balance conditions, which may not be exercised in routine testing. The vulnerability belongs to the class of balance‑mismanagement bugs that lead to arithmetic underflows and denial‑of‑service of reward functions. To remediate, the contract should record the caller’s balance (msg.sender) before the transfer, or avoid recomputing usdtAmount altogether and rely on the known usdtAmount value. Correcting the address used for the balance query restores proper accounting, prevents the underflow, and ensures that users receive the expected USDT rewards and that the Claim event reflects the true transferred amount.
