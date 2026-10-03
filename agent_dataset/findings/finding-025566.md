---
id: 25566
severity: "Medium"
---

# maxDeposit doesn't comply with ERC-4626

## Description



## Proof of Concept

Add the following test inside `pt-v5-vault/test/unit/PrizeVault/PrizeVault.t.sol`

```solidity
    function testHash_MaxDepositRevertLossy() public {
        PrizeVault testVault=  new PrizeVault(
            "PoolTogether aEthDAI Prize Token (PTaEthDAI)",
            "PTaEthDAI",
            yieldVault,
            PrizePool(address(prizePool)),
            claimer,
            address(this),
            YIELD_FEE_PERCENTAGE,
            0,
            address(this)
        );

        underlyingAsset.mint(address(yieldVault),100e18);
        YieldVault(address(yieldVault)).mint(address(100),99e18); // 99 shares , 100 assets

        uint maxDepositReturned = testVault.maxDeposit(address(this));

        uint amount_ = 99e18;
        underlyingAsset.mint(address(this),amount_);
        underlyingAsset.approve(address(testVault),amount_);

        assert(maxDepositReturned > amount_);

        vm.expectRevert();
        testVault.deposit(amount_,address(this));

    }
```

## Vulnerability Detail

The contract's `maxDeposit` function doesn't comply with ERC-4626 which is a mentioned requirement. According to the [specification](<https://eips.ethereum.org/EIPS/eip-4626#maxdeposit>), `MUST return the maximum amount of assets deposit would allow to be deposited for receiver and not cause a revert ....` The `deposit` function will revert in case the deposit is a lossy deposit ie. totalPreciseAsset function returns less than the totalDebt after the deposit. It is possible for this to occur due to rounding inside the preview redeem function of the yieldVault in the absence / depletion of yield buffer

## Code Snippet

[https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-vault/src/PrizeVault.sol#L991-L992](<https://github.com/sherlock-audit/2024-05-pooltogether/blob/1aa1b8c028b659585e4c7a6b9b652fb075f86db3/pt-v5-vault/src/PrizeVault.sol#L991-L992>)

## Recommendation

Consider the yieldBuffer balance too inside the `maxDeposit` function
