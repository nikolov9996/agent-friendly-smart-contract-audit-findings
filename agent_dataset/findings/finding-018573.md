---
id: 18573
severity: "High"
---

# `redeem`

## Description

Using the wrong owner parameter can cause users to lose rewards.

## Proof of Concept

In `TalosStrategyStaked.sol`, if the user’s `shares` have changed, we need to call `flywheel.accrue()` first, which will accrue `rewards` and update the corresponding `userIndex`. This way, we can ensure the accuracy of `rewards`. So we will call `flywheel.accrue()` before `beforeDeposit`/`beforeRedeem`/transfer etc.

Take `redeem()` as an example, the code is as follows:
```solidity
    contract TalosStrategyStaked is TalosStrategySimple, ITalosStrategyStaked {
    ...

        function beforeRedeem(uint256 _tokenId, address _owner) internal override {
            _earnFees(_tokenId);
            flywheel.accrue(_owner);
        }
```
But when `beforeRedeem()` is called with the wrong owner passed in. The `redeem()` code is as follows:
```solidity
        function redeem(uint256 shares, uint256 amount0Min, uint256 amount1Min, address receiver, address _owner)
            public
            virtual
            override
            nonReentrant
            checkDeviation
            returns (uint256 amount0, uint256 amount1)
        {
    ...
            if (msg.sender != _owner) {
                uint256 allowed = allowance[_owner][msg.sender]; // Saves gas for limited approvals.

                if (allowed != type(uint256).max) allowance[_owner][msg.sender] = allowed - shares;
            }

            if (shares == 0) revert RedeemingZeroShares();
            if (receiver == address(0)) revert ReceiverIsZeroAddress();

            uint256 _tokenId = tokenId;
            beforeRedeem(_tokenId, receiver);

            INonfungiblePositionManager _nonfungiblePositionManager = nonfungiblePositionManager; // Saves an extra SLOAD
            {
                uint128 liquidityToDecrease = uint128((liquidity * shares) / totalSupply);

                (amount0, amount1) = _nonfungiblePositionManager.decreaseLiquidity(
                    INonfungiblePositionManager.DecreaseLiquidityParams({
                        tokenId: _tokenId,
                        liquidity: liquidityToDecrease,
                        amount0Min: amount0Min,
                        amount1Min: amount1Min,
                        deadline: block.timestamp
                    })
                );

                if (amount0 == 0 && amount1 == 0) revert AmountsAreZero();

                _burn(_owner, shares);

                liquidity -= liquidityToDecrease;
            }
```
From the above code, we see that the parameter is the `receiver`, but the person whose shares are burned is `_owner`.

We need to accrue `_owner`, not `receiver`. This leads to a direct reduction of the user’s shares without `accrue`, and the user loses the corresponding rewards.

## Recommendation

```solidity
function redeem(uint256 shares, uint256 amount0Min, uint256 amount1Min, address receiver, address _owner)
        public
        virtual
        override
        nonReentrant
        checkDeviation
        returns (uint256 amount0, uint256 amount1)
    {
        if (msg.sender != _owner) {
            uint256 allowed = allowance[_owner][msg.sender]; // Saves gas for limited approvals.

            if (allowed != type(uint256).max) allowance[_owner][msg.sender] = allowed - shares;
        }

        if (shares == 0) revert RedeemingZeroShares();
        if (receiver == address(0)) revert ReceiverIsZeroAddress();

        uint256 _tokenId = tokenId;
        beforeRedeem(_tokenId, _owner);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect owner reference passed to the reward‑accrual hook during a token redemption operation. The contract’s redeem routine accepts a receiver address and an explicit owner address, but when it invokes the internal beforeRedeem hook it supplies the receiver instead of the true owner whose shares are being burned. The beforeRedeem hook is responsible for calling the flywheel accrual function, which updates the pending reward balance for the supplied address. Because the hook receives the receiver, the actual owner’s pending rewards are never accrued before the shares are destroyed. Consequently, the owner’s reward accounting is out of sync: the contract reduces the owner’s share balance without first crediting the earned rewards, leading to a loss of those rewards. This can be exploited simply by calling redeem with a receiver that differs from the owner, which is a legitimate use‑case for transferring redeemed assets to a third party. The exploit does not require any special permissions; any user who redeems to an address other than themselves will suffer the reward loss. The impact is a reduction of the user’s expected earnings – users may see their reward balance stay unchanged while their share balance drops, effectively “funds disappear” from their perspective. The bug manifests whenever the redeem function is invoked with a non‑zero receiver that is not the same as the owner, which is common in protocols that allow third‑party withdrawals or proxy contracts. All participants who hold redeemable shares are affected, especially those who rely on accurate reward accounting. The issue was discovered during a manual audit that examined the flow of reward accrual and noticed that the owner argument was incorrectly forwarded to the hook. It can be hard to notice because the transaction still succeeds, the user receives the underlying assets, and the missing rewards are only observable by checking the reward balance after redemption. The proper fix is to pass the true owner address to the beforeRedeem hook (or redesign the hook to derive the owner from the burned shares) so that rewards are accrued for the correct account before any share reduction occurs. This aligns the accounting logic with the business rule that rewards must be calculated on the exact holdings that are being removed, preventing silent loss of earned incentives.
