---
id: 21683
severity: "High"
---

# Incorrect accounting bug of the `yDUSD` vault leads to total loss of depositors’ `DUSD` assets

## Description

The current implementation of the `yDUSD` vault does not properly support the auto-compounding token rewards mechanism by directly minting the `DUSD` assets to the vault.

Due to an incorrect accounting bug of the vault’s total supply (shares), depositors can lose some deposited `DUSD` assets (principal) or even all the assets when the `Ditto` protocol mints `DUSD` debts to the vault to account for any discounts.

When the match price is below the oracle price, the `OrdersFacet::_matchIsDiscounted()` will be invoked to account for a discount [by minting the discount (`newDebt`)](https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/facets/OrdersFacet.sol#L178) (`@1` in the snippet below) to the `yDUSD` vault.

Assuming the `yDUSD` vault is empty (i.e., both `totalAssets` and `totalSupply` are 0), for simplicity’s sake. This step will increase the vault’s total `DUSD` assets (`totalAssets` — spot balance) without updating the vault’s total supply (`totalSupply` — tracked shares).

```solidity
function _matchIsDiscounted(MTypes.HandleDiscount memory h) external onlyDiamond {
    ...

    if (pctOfDiscountedDebt > C.DISCOUNT_THRESHOLD && !LibTStore.isForcedBid()) {
        ...

        // @dev Increase global ercDebt to account for the increase debt owed by shorters
        uint104 newDebt = uint104(ercDebtMinusTapp.mul(discountPenaltyFee));
        Asset.ercDebt += newDebt;
        Asset.ercDebtFee += uint88(newDebt); // should be uint104?

        // @dev Mint dUSD to the yDUSD vault for
        // Note: Does not currently handle mutli-asset
@1      IERC20(h.asset).mint(s.yieldVault[h.asset], newDebt);
            //@audit @1 -- When the match price is below the oracle price, the _matchIsDiscounted()
            //             will be invoked to account for a discount by minting the discount (newDebt)
            //             to the yDUSD vault.
            //
            //             Assuming that the yDUSD vault is empty (i.e., totalAssets and totalSupply are 0), 
            //             for simplicity's sake.
            //
            //             This step will increase the vault's total DUSD assets (totalAssets -- spot balance)
            //             without updating the vault's total supply (totalSupply -- tracked shares).
    }
}
```

* `@1`: <https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/facets/OrdersFacet.sol#L178>

After `@1`, when a user deposits their `DUSD` assets to the `yDUSD` vault, the [`ERC4626::previewDeposit()`](https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/tokens/yDUSD.sol#L69) (`@2` in the snippet below) will be executed to calculate the shares based on the deposited assets.

An incorrect accounting bug of the vault’s total supply (tracked shares) occurs in `@1` above. In this example, the calculated shares will be 0 since the `totalSupply` is 0 (if the `totalSupply` != 0, the calculated shares can be less than expected). For more details, refer to `@2.1` below.

Since the calculated shares == 0, the user [will receive 0 shares and lose all deposited `DUSD` assets](https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/tokens/yDUSD.sol#L72) (`@3`). Even the [slippage protection check](https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/tokens/yDUSD.sol#L77) (`@4`) cannot detect the invalid calculation due to the `slippage.mul(shares)` == 0, and the user’s tracked shares remain unchanged. _(Actually, I discovered another issue regarding the slippage protection check, which will be reported separately.)_

```solidity
function deposit(uint256 assets, address receiver) public override returns (uint256) {
    if (assets > maxDeposit(receiver)) revert Errors.ERC4626DepositMoreThanMax();

    //@audit @2 -- After @1, when a user deposits their DUSD assets to the yDUSD vault, the previewDeposit()
    //             will be executed to calculate the shares based on the deposited assets.
    //
    //             Due to an incorrect accounting bug of the vault's total supply (tracked shares) occurs in @1,
    //             the calculated shares, in this case, will be 0 since totalSupply is 0 (if totalSupply != 0, 
    //             the calculated shares can be less than expected). For more details, refer to @2.1.
@2  uint256 shares = previewDeposit(assets);

    uint256 oldBalance = balanceOf(receiver);
    //@audit @3 -- Since the calculated shares == 0, the user will receive 0 shares. Thus, they will lose all
    //             deposited DUSD assets.
@3  _deposit(_msgSender(), receiver, assets, shares);
    uint256 newBalance = balanceOf(receiver);

    // @dev Slippage is likely irrelevant for this. Merely for preventative purposes
    uint256 slippage = 0.01 ether;
@4  if (newBalance < slippage.mul(shares) + oldBalance) revert Errors.ERC4626DepositSlippageExceeded();
        //@audit @4 -- Even the slippage protection check above cannot detect the invalid calculation since
        //             the slippage.mul(shares) == 0, and the user's tracked shares remain unchanged.

    return shares;
}
```

* `@2`: <https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/tokens/yDUSD.sol#L69>
* `@3`: <https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/tokens/yDUSD.sol#L72>
* `@4`: <https://github.com/code-423n4/2024-07-dittoeth/blob/ca3c5bf8e13d0df6a2c1f8a9c66ad95bbad35bce/contracts/tokens/yDUSD.sol#L77>

To calculate the user’s shares, the `ERC4626::previewDeposit()` calls the [`ERC4626::_convertToShares()`](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/4fd2f8be339e850c32206342c3f9a1a7bedbb204/contracts/token/ERC20/extensions/ERC4626.sol#L134) (`@2.1` in the snippet below).

The [calculated shares will be 0 (due to the rounding down)](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/4fd2f8be339e850c32206342c3f9a1a7bedbb204/contracts/token/ERC20/extensions/ERC4626.sol#L200) (`@2.2`) because the `ERC20::totalSupply()` will return 0 (the vault’s tracked total shares) while the `ERC4626::totalAssets()` will return the previously minted discount amount (i.e., the `newDebt` from `@1`). Refer to the `@2.2` for a detailed explanation of the calculation.

```solidity
// FILE: node_modules/@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol
function previewDeposit(uint256 assets) public view virtual override returns (uint256) {
    //@audit @2.1 -- The previewDeposit() calls the _convertToShares() to calculate the shares.
@2.1    return _convertToShares(assets, Math.Rounding.Down);
}

// FILE: node_modules/@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol
function _convertToShares(uint256 assets, Math.Rounding rounding) internal view virtual returns (uint256) {
    //@audit @2.2 -- The calculated shares, in this case, will be 0 (due to the rounding down) 
    //               because the totalSupply() will return 0 (the vault's tracked total shares) 
    //               while the totalAssets() will return the previously minted discount amount 
    //               (i.e., the newDebt from @1).
    //
    //                shares = assets * (0 + 10 ** 0) / newDebt
    //                       = assets * 1 / newDebt (e.g., assets < newDebt)
    //                       = 0 (due to rounding down)
@2.2    return assets.mulDiv(totalSupply() + 10 ** _decimalsOffset(), totalAssets() + 1, rounding);
}
```

* `@2.1`: <https://github.com/OpenZeppelin/openzeppelin-contracts/blob/4fd2f8be339e850c32206342c3f9a1a7bedbb204/contracts/token/ERC20/extensions/ERC4626.sol#L134>
* `@2.2`: <https://github.com/OpenZeppelin/openzeppelin-contracts/blob/4fd2f8be339e850c32206342c3f9a1a7bedbb204/contracts/token/ERC20/extensions/ERC4626.sol#L200>

As you can see, the `ERC20::totalSupply()` returns the [vault’s tracked total shares (0)](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/4fd2f8be339e850c32206342c3f9a1a7bedbb204/contracts/token/ERC20/ERC20.sol#L94) (`@2.2.1` in the snippet below), and `ERC4626::totalAssets()` returns the [previously minted discount amount (i.e., the `newDebt` from `@1`)](https://github.com/OpenZeppelin/openzeppelin-contracts/blob/4fd2f8be339e850c32206342c3f9a1a7bedbb204/contracts/token/ERC20/extensions/ERC4626.sol#L99) (`@2.2.2`).

```solidity
// FILE: node_modules/@openzeppelin/contracts/token/ERC20/ERC20.sol
function totalSupply() public view virtual override returns (uint256) {
    //@audit @2.2.1 -- The totalSupply() returns the vault's tracked total shares (0).
@2.2.1  return _totalSupply; //@audit -- tracked shares
}

// FILE: node_modules/@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol
function totalAssets() public view virtual override returns (uint256) {
    //@audit @2.2.2 -- The totalAssets() returns the previously minted discount amount 
    //                 (i.e., the newDebt from @1).
@2.2.2  return _asset.balanceOf(address(this)); //@audit -- spot balance
}
```

* `@2.2.1`: <https://github.com/OpenZeppelin/openzeppelin-contracts/blob/4fd2f8be339e850c32206342c3f9a1a7bedbb204/contracts/token/ERC20/ERC20.sol#L94>
* `@2.2.2`: <https://github.com/OpenZeppelin/openzeppelin-contracts/blob/4fd2f8be339e850c32206342c3f9a1a7bedbb204/contracts/token/ERC20/extensions/ERC4626.sol#L99>

Depositors can lose some deposited `DUSD` assets (principal) or whole assets when the `Ditto` protocol mints `DUSD` debts to the `yDUSD` vault to account for discounts.

## Proof of Concept

This section provides a coded PoC.

Place the `test_PoC_yDUSD_Yault_totalSupply_IncorrectInternalAccounting()` in the `.test/YDUSD.t.sol` file and run the test using the command: `forge test -vv --mt test_PoC_yDUSD_Yault_totalSupply_IncorrectInternalAccounting`.

The PoC shows that a user loses all `DUSD` assets (both principal and yield) when he deposits the assets into the `yDUSD` vault right after the protocol has minted debts to the vault.

```solidity
function test_PoC_yDUSD_Yault_totalSupply_IncorrectInternalAccounting() public {
    // Create discounts to generate newDebt
    uint88 newDebt = uint88(discountSetUp());
    assertEq(rebasingToken.totalAssets(), newDebt);
    assertEq(rebasingToken.totalSupply(), 0);
    assertEq(rebasingToken.balanceOf(receiver), 0);
    assertEq(rebasingToken.balanceOf(_diamond), 0);
    assertEq(rebasingToken.balanceOf(_yDUSD), 0);
    assertEq(token.balanceOf(_yDUSD), newDebt);

    // Receiver deposits DUSD into the vault to get yDUSD
    vm.prank(receiver);
    rebasingToken.deposit(DEFAULT_AMOUNT, receiver);

    assertEq(rebasingToken.totalAssets(), DEFAULT_AMOUNT + newDebt);
    assertEq(rebasingToken.totalSupply(), 0);       // 0 amount due to the invalid accounting bug of totalSupply
    assertEq(rebasingToken.balanceOf(receiver), 0); // 0 amount due to the invalid accounting bug of totalSupply
    assertEq(rebasingToken.balanceOf(_diamond), 0);
    assertEq(rebasingToken.balanceOf(_yDUSD), 0);
    assertEq(token.balanceOf(_yDUSD), DEFAULT_AMOUNT + newDebt);

    // Match at oracle
    fundLimitBidOpt(DEFAULT_PRICE, DEFAULT_AMOUNT, extra);
    fundLimitAskOpt(DEFAULT_PRICE, DEFAULT_AMOUNT, extra);

    skip(C.DISCOUNT_WAIT_TIME);

    // Receiver expects to withdraw yDUSD and get back more DUSD than the original amount (Expect Revert!!!)
    // @dev Roughly DEFAULT_AMOUNT + newDebt, but rounded down
    uint88 withdrawAmountReceiver = 54999999999999999999990;
    vm.prank(receiver);
    vm.expectRevert(Errors.ERC4626WithdrawMoreThanMax.selector); // Expect Revert!!!
    rebasingToken.proposeWithdraw(withdrawAmountReceiver);

    // 0 amount due to the invalid accounting bug of totalSupply
    assertEq(rebasingToken.maxWithdraw(receiver), 0);
}
```

## Recommendation

Rework the `yDUSD` vault by applying the concept of a single-sided auto-compounding token rewards mechanism of the [xERC4626](https://github.com/ERC4626-Alliance/ERC4626-Contracts/blob/main/src/xERC4626.sol), which is fully compatible with the `ERC4626` and ultimately maintains balances using internal accounting to prevent instantaneous changes in the exchange rate.

_Note: see[original submission](https://github.com/code-423n4/2024-07-dittoeth-findings/issues/7) for full discussion._

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an incorrect accounting bug in the yDUSD vault that breaks the ERC4626 accounting model when the Ditto protocol mints DUSD debt to the vault as a discount. When the match price falls below the oracle price, the OrdersFacet::_matchIsDiscounted() function mints newDebt DUSD directly into the vault without adjusting the vault’s totalSupply, which represents the tracked share balance. As a result the vault’s totalAssets (the spot DUSD balance) increases while totalSupply remains zero. ERC4626::previewDeposit() subsequently calls _convertToShares() with a totalSupply of zero and a non‑zero totalAssets, causing the share calculation to round down to zero. Depositors therefore receive zero yDUSD shares for any amount of DUSD they deposit, effectively losing their principal and any accrued yield. The slippage protection check does not flag the error because it multiplies the zero share amount by the slippage factor, also yielding zero. This bug manifests only after a discount minting event and can affect any user who deposits DUSD into the vault under those conditions, leading to total loss of funds. The issue was discovered during a formal audit by Code4rena and reproduced with a PoC test that shows a user’s balance remaining zero despite a successful deposit call. The problem is hard to notice because the transaction does not revert and the vault’s external balance appears to increase, while the internal share accounting silently fails. The root cause is the failure to update the vault’s share accounting when external assets are minted into the vault, breaking the invariant that totalSupply and totalAssets move together. To fix the issue the vault should adopt a proper single‑sided auto‑compounding accounting scheme such as the xERC4626 design, ensuring that any minted assets are reflected in both totalAssets and totalSupply or that the exchange rate is adjusted atomically, thereby preserving the accounting invariant and preventing users from receiving zero shares.
