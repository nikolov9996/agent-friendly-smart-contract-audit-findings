---
id: 21541
severity: "Medium"
---

# Multicall does not work as intended

## Description

The `multicall(bytes[] calldata _data)` function in the Size.sol contract does not work as intended. The intention of the `multicall(bytes[] calldata _data)` function is to allow users to access multiple functionalities of the Size protocol, such as a (deposit and repay) pair, by a single transaction to Size.sol:

```solidity
function multicall(bytes[] calldata _data)
    public
    payable
    override(IMulticall)
    whenNotPaused
    returns (bytes[] memory results)
{
    results = state.multicall(_data);
}
```

The multicall function allows batch processing of multiple interactions with the protocol in a single transaction. This also allows users to take actions that would otherwise be denied due to deposit limits. One of these actions is a (deposit and repay) pair.

Let’s say a credit-debt pair exists. Assume that the tenor of the debt is 1 year and the future value is `100ke6` USDC. Let’s say the borrower decides to repay the loan just 1 day before the maturity ends. During this 1 year, the total supply of `borrowAToken` had increased so much that the total supply of `borrowAToken` was just `10e6` USDC worth below the cap (that is, just below the cap) at the time when the borrower decided to repay the loan.

To repay a loan, Size requires the user to have sufficient `borrowAToken`:

```solidity
function executeRepay(State storage state, RepayParams calldata params) external {
    DebtPosition storage debtPosition = state.getDebtPosition(params.debtPositionId);

    state.data.borrowAToken.transferFrom(msg.sender, address(this), debtPosition.futureValue);
    debtPosition.liquidityIndexAtRepayment = state.data.borrowAToken.liquidityIndex();
    state.repayDebt(params.debtPositionId, debtPosition.futureValue);

    emit Events.Repay(params.debtPositionId);
}
```

The user achieves this by first depositing the required amount of underlying borrow tokens (here, USDC) and then calling the `repay(RepayParams calldata params)` function:

```solidity
function depositUnderlyingBorrowTokenToVariablePool(State storage state, address from, address to, uint256 amount)
    external
{
    state.data.underlyingBorrowToken.safeTransferFrom(from, address(this), amount);

    IAToken aToken =
        IAToken(state.data.variablePool.getReserveData(address(state.data.underlyingBorrowToken)).aTokenAddress);

    uint256 scaledBalanceBefore = aToken.scaledBalanceOf(address(this));

    state.data.underlyingBorrowToken.forceApprove(address(state.data.variablePool), amount);
    state.data.variablePool.supply(address(state.data.underlyingBorrowToken), amount, address(this), 0);

    uint256 scaledAmount = aToken.scaledBalanceOf(address(this)) - scaledBalanceBefore;

    state.data.borrowAToken.mintScaled(to, scaledAmount);
}
```

Now, in our case, when the borrower decides to deposit `100ke6` USDC (at max if it would have some existing `borrowAToken`), he would not be able to do so (as the cap would be hit by depositing just `10e6` USDC). The situation is that the tenor is about to end (1 day left) and the borrower is not able to repay, not because he does not have money, but because `borrowAToken`’s total supply cap does not allow him to deposit enough USDC.

To mitigate this, Size provides the multicall function, that bypasses the deposit limit and allows users to carry out such actions (LOC-80 in Deposit.sol):

```solidity
function executeDeposit(State storage state, DepositParams calldata params) public {
    address from = msg.sender;
    uint256 amount = params.amount;
    if (msg.value > 0) {
        // do not trust msg.value (see `Multicall.sol`)
        amount = address(this).balance;
        // slither-disable-next-line arbitrary-send-eth
        state.data.weth.deposit{value: amount}();
        state.data.weth.forceApprove(address(this), amount);
        from = address(this);
    }

    if (params.token == address(state.data.underlyingBorrowToken)) {
        state.depositUnderlyingBorrowTokenToVariablePool(from, params.to, amount);
        // borrow aToken cap is not validated in multicall,
        //   since users must be able to deposit more tokens to repay debt
        if (!state.data.isMulticall) {
            state.validateBorrowATokenCap();
        }
    } else {
        state.depositUnderlyingCollateralToken(from, params.to, amount);
    }

    emit Events.Deposit(params.token, params.to, amount);
}
```

Let’s say a user uses the multicall function for a (deposit and repay) pair action. The multicall function checks for an invariant that restricts users from depositing more `borrowATokens` than required to repay the loan by restricting:

        increase in borrowAToken supply <= decrease in debtToken supply

```solidity
function validateBorrowATokenIncreaseLteDebtTokenDecrease(
    State storage state,
    uint256 borrowATokenSupplyBefore,
    uint256 debtTokenSupplyBefore,
    uint256 borrowATokenSupplyAfter,
    uint256 debtTokenSupplyAfter
) external view {
    // If the supply is above the cap
    if (borrowATokenSupplyAfter > state.riskConfig.borrowATokenCap) {
        uint256 borrowATokenSupplyIncrease = borrowATokenSupplyAfter > borrowATokenSupplyBefore
            ? borrowATokenSupplyAfter - borrowATokenSupplyBefore
            : 0;
        uint256 debtATokenSupplyDecrease =
            debtTokenSupplyBefore > debtTokenSupplyAfter ? debtTokenSupplyBefore - debtTokenSupplyAfter : 0;

        // and the supply increase is greater than the debt reduction
        if (borrowATokenSupplyIncrease > debtATokenSupplyDecrease) {
            // revert
            revert Errors.BORROW_ATOKEN_INCREASE_EXCEEDS_DEBT_TOKEN_DECREASE(
                borrowATokenSupplyIncrease, debtATokenSupplyDecrease
            );
        }
        // otherwise, it means the debt reduction was greater than the inflow of cash: do not revert
    }
    // otherwise, the supply is below the cap: do not revert
}
```

The problem is, this is the exact invariant that is broken. The PoC below explains how in detail.

## Proof of Concept

I have provided a thorough step-by-step PoC to explain how the invariant is broken. Let’s continue with our previous example.

Let’s say the `borrowAToken` cap is `1Me6` and its current supply is `990ke6`. Before calling the multicall function, the `borrowAToken` balances are:

* borrower = 0
* Size contract = 0
* Total supply of `borrowAToken` = `990ke6`

Also, before calling the multicall function:

        debtToken.balanceOf[borrower] = 100ke6

The borrower calls the multicall function, with (deposit and repay) action pair in Size.sol:

```solidity
function multicall(bytes[] calldata _data)
    public
    payable
    override(IMulticall)
    whenNotPaused
    returns (bytes[] memory results)
{
    results = state.multicall(_data);
}
```

To make things simple to understand, let’s assume that this is the first repayment of a loan; that is, other credit-debt pairs exist but have sufficient time to mature.

The borrower has used the multicall to deposit `500ke6` USDC and would want to repay his debt completely (`100ke6` USDC). The deposit action would be performed (as the deposit limit check is bypassed). After the deposit is over, the `borrowAToken` balances would be:

* borrower = 500ke6 (actually, it would be ~500ke6 due to calculations involving AToken and liquidity index, but, I have used 500ke6 for simplicity).
* Size contract = 0
* Total supply of `borrowAToken` = `1.49Me6`

After the repayment is over, the borrowAToken balances are:

* borrower = `400ke6`
* Size contract = `100ke6`
* Total supply of `borrowAToken` = `1.49Me6`

Also, after repayment:

        debtToken.balanceOf[borrower] = 0

Now, the above situation breaks the invariant:

        increase in borrowAToken supply (= 500ke6) is not <= decrease in debtToken supply (= 100ke6)

The multicall flow should revert. However, if we look at the `multicall(State storage state, bytes[] calldata data)` function in Multicall.sol:

```solidity
function multicall(State storage state, bytes[] calldata data) internal returns (bytes[] memory results) {
    state.data.isMulticall = true;

    uint256 borrowATokenSupplyBefore = state.data.borrowAToken.balanceOf(address(this));
    uint256 debtTokenSupplyBefore = state.data.debtToken.totalSupply();

    results = new bytes[](data.length);
    for (uint256 i = 0; i < data.length; i++) {
        results[i] = Address.functionDelegateCall(address(this), data[i]);
    }

    uint256 borrowATokenSupplyAfter = state.data.borrowAToken.balanceOf(address(this));
    uint256 debtTokenSupplyAfter = state.data.debtToken.totalSupply();

    state.validateBorrowATokenIncreaseLteDebtTokenDecrease(
        borrowATokenSupplyBefore, debtTokenSupplyBefore, borrowATokenSupplyAfter, debtTokenSupplyAfter
    );

    state.data.isMulticall = false;
}
```

LOC-29 sets the `borrowATokenSupplyBefore` variable to `borrowAToken.balanceOf(Size_contract)`:

    uint256 borrowATokenSupplyBefore = state.data.borrowAToken.balanceOf(address(this));

LOC-37 sets the `borrowATokenSupplyAfter` variable to `borrowAToken.balanceOf(Size_contract)`:

    uint256 borrowATokenSupplyAfter = state.data.borrowAToken.balanceOf(address(this));

As per our example:

    uint256 borrowATokenSupplyBefore = 0
    uint256 borrowATokenSupplyAfter = 100ke6

Now, `validateBorrowATokenIncreaseLteDebtTokenDecrease()` is called at LOC-40:

```solidity
function validateBorrowATokenIncreaseLteDebtTokenDecrease(
    State storage state,
    uint256 borrowATokenSupplyBefore,
    uint256 debtTokenSupplyBefore,
    uint256 borrowATokenSupplyAfter,
    uint256 debtTokenSupplyAfter
) external view {
    // If the supply is above the cap
    if (borrowATokenSupplyAfter > state.riskConfig.borrowATokenCap) {
        uint256 borrowATokenSupplyIncrease = borrowATokenSupplyAfter > borrowATokenSupplyBefore
            ? borrowATokenSupplyAfter - borrowATokenSupplyBefore
            : 0;
        uint256 debtATokenSupplyDecrease =
            debtTokenSupplyBefore > debtTokenSupplyAfter ? debtTokenSupplyBefore - debtTokenSupplyAfter : 0;

        // and the supply increase is greater than the debt reduction
        if (borrowATokenSupplyIncrease > debtATokenSupplyDecrease) {
            // revert
            revert Errors.BORROW_ATOKEN_INCREASE_EXCEEDS_DEBT_TOKEN_DECREASE(
                borrowATokenSupplyIncrease, debtATokenSupplyDecrease
            );
        }
        // otherwise, it means the debt reduction was greater than the inflow of cash: do not revert
    }
    // otherwise, the supply is below the cap: do not revert
}
```

In this function, the first `if()` statement at LOC-27 would be executed, as per our example:

        if(100ke6 > 1Me6)

… which would be false.

Therefore, the control flow does not move in the `if()` block, and the protocol assumes “the supply is below the cap: do not revert”. As a result, the multicall function would not revert.

The root cause of this issue is the use of `state.data.borrowAToken.balanceOf(address(this))` to set variables `borrowATokenSupplyBefore` and `borrowATokenSupplyAfter`. Instead of `state.data.borrowAToken.balanceOf(address(this))`, `state.data.borrowAToken.totalSupply()` should be used. This would work as then:

        borrowATokenSupplyBefore would be 990ke6
        borrowATokenSupplyAfter would be 1.49Me6

And, in the `if()` block of `validateBorrowATokenIncreaseLteDebtTokenDecrease()` function, we would have:

        if(1.49Me6 > 1Me6)

… which would be true. Thus, the control flow would enter into the `if()` block. At LOC-35, we would have:

                // and the supply increase is greater than the debt reduction
                if (borrowATokenSupplyIncrease > debtATokenSupplyDecrease) {
                    // revert
                    revert Errors.BORROW_ATOKEN_INCREASE_EXCEEDS_DEBT_TOKEN_DECREASE(
                        borrowATokenSupplyIncrease, debtATokenSupplyDecrease
                    );
                }

That is:

        if(500ke6 > 100ke6)

… which would be true again and finally, the transaction would revert.

This root cause gives rise to one more issue:

* A user would use the multicall for a deposit action only but would be able to bypass the deposit limit.

To comprehend this, think of a similar situation as above where:

* The cap of `borrorAToken` supply = `1Me6`
* Current total supply of `borrowAToken` = `990ke6`

Moreover, to keep things simple, let’s assume that:

        borrowToken.balanceOf[Size_contract] = 0

Now, a user deposits `200ke6` USDC using the multicall function. The normal (that is, without multicall) USDC deposit flow contains a logic to check for the deposit limit, which is bypassed when a multicall is used:

                if (!state.data.isMulticall) {
                    state.validateBorrowATokenCap();
                }

After completing the deposit, the multicall function would call the `validateBorrowATokenIncreaseLteDebtTokenDecrease()` function for a check (similar to above). The following arguments would have the specified value:

                uint256 borrowATokenSupplyBefore = borrowToken.balanceOf[Size_contract] = 0
                uint256 borrowATokenSupplyAfter = borrowToken.balanceOf[Size_contract] = 0

Now, again in the `if()` block at LOC-27:

            if (borrowATokenSupplyAfter > state.riskConfig.borrowATokenCap)

We would have the following:

        if(0 > 1Me6)

… which would be false, and, so, the control flow would not enter the `if()` block. Thus, the multicall flow would pass with the following result:

* Current total supply of `borrowAToken` = `1.19Me6`
* The cap of total supply of `borrowAToken` = `1Me6`

The user was successful in depositing USDC in spite of the fact that his deposit crossed the deposit limit.

## Recommendation

Apply the following in `multicall(State storage state, bytes[] calldata data)` function:

```solidity
function multicall(State storage state, bytes[] calldata data) internal returns (bytes[] memory results) {
    state.data.isMulticall = true;

    uint256 borrowATokenSupplyBefore = state.data.borrowAToken.totalSupply();
    uint256 debtTokenSupplyBefore = state.data.debtToken.totalSupply();

    results = new bytes[](data.length);
    for (uint256 i = 0; i < data.length; i++) {
        results[i] = Address.functionDelegateCall(address(this), data[i]);
    }

    uint256 borrowATokenSupplyAfter = state.data.borrowAToken.totalSupply();
    uint256 debtTokenSupplyAfter = state.data.debtToken.totalSupply();

    state.validateBorrowATokenIncreaseLteDebtTokenDecrease(
        borrowATokenSupplyBefore, debtTokenSupplyBefore, borrowATokenSupplyAfter, debtTokenSupplyAfter
    );

    state.data.isMulticall = false;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The Size protocol provides a multicall entry point that is meant to let a user combine several actions – for example a deposit of underlying borrow tokens followed by a repayment – in a single transaction. The intended behaviour is to bypass the normal borrowAToken cap check during the deposit, but to enforce an invariant after the batch finishes: the increase in the total supply of borrowAToken must never exceed the decrease in the total supply of the corresponding debt token. The implementation of this invariant is flawed because the multicall routine records the borrowAToken supply before and after the batch using the contract’s own balance (borrowAToken.balanceOf(address(this))) instead of the global totalSupply() value. When a user deposits via multicall, the contract’s own balance remains zero, so the recorded “supply before” and “supply after” both appear to be zero. Consequently the invariant check sees no increase and never enters the branch that would compare the increase to the debt reduction, even though the real total supply of borrowAToken has grown beyond the configured cap. This allows a malicious or careless user to deposit an amount that pushes the global borrowAToken supply over its cap, or to combine a large deposit with a repayment that mints extra borrowAToken without triggering a revert. From a user’s perspective the UI may show a successful deposit or repayment even though the protocol’s accounting rules should have blocked the operation; the user may see their borrow token balance increase unexpectedly or may be able to repay a loan that would otherwise be rejected due to the cap. The impact is a breach of the protocol’s accounting guarantees: the borrowAToken cap, which is meant to limit exposure, can be bypassed, leading to token inflation, potential loss of value for other token holders, and a weakening of the protocol’s risk controls. The bug manifests only when the multicall path is used, particularly for deposit‑and‑repay pairs or for deposits alone, and only when the borrowAToken supply is close to the cap. It was discovered during a formal audit by analysing the state variables used in the invariant validation. The issue is hard to notice because the contract’s own token balance is naturally zero, making the faulty check appear correct at a glance. The proper fix is to measure the borrowAToken supply with totalSupply() both before and after the multicall, ensuring the invariant sees the true increase and reverts when the cap would be exceeded. Conceptually, this is an invariant‑violation bug caused by using an incorrect state snapshot in a batch operation, allowing a cap‑bypass and unintended token minting.
