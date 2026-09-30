---
id: 18436
severity: "High"
---

# `FeeWrapper` fails to handle ETH payment refunds

## Description

The `FeeWrapper` contract can be used to wrap calls that include ETH payments. This is handled by the `_rubicallPayable` function:
```solidity
function _rubicallPayable(
    CallParams memory _params
) internal returns (bytes memory) {
    // charge fee from feeParams
    uint256 _msgValue = _chargeFeePayable(_params.feeParams);

    (bool _OK, bytes memory _data) = _params.target.call{value: _msgValue}(
        bytes.concat(_params.selector, _params.args)
    );

    require(_OK, "low-level call to the router failed");

    return _data;
}
```

As we can see in the previous snippet, the implementation will forward the ETH payment (minus fees) to the target contract. If the target contract ends up using less ETH than the sent amount, then the usual approach would be to refund the remaining ETH back to the caller, which is a normal and common operation.

If this is the case, then the wrapped call will fail as the `FeeWrapper` doesn’t implement the `receive` or `fallback` function to allow ETH payments. Even though there is no loss of funds as the transaction is reverted, the issue will prevent users from wrapping calls to target contracts that may refund ETH as part of their normal behavior.

As a potential real example, we can the explore the `buyAllAmountWithETH` function present in the `RubiconRouter` contract:
```solidity
function buyAllAmountWithETH(
    ERC20 buy_gem,
    uint256 buy_amt,
    uint256 max_fill_amount
) external payable beGoneReentrantScum returns (uint256 fill) {
    address _weth = address(wethAddress);
    uint256 _before = ERC20(_weth).balanceOf(address(this));
    require(
        msg.value == max_fill_amount,
        "must send as much ETH as max_fill_amount"
    );
    IWETH(wethAddress).deposit{value: max_fill_amount}(); // Pay with native ETH -> WETH

    if (
        IWETH(wethAddress).allowance(address(this), RubiconMarketAddress) <
        max_fill_amount
    ) {
        approveAssetOnMarket(wethAddress);
    }

    // An amount in WETH
    fill = RubiconMarket(RubiconMarketAddress).buyAllAmount(
        buy_gem,
        buy_amt,
        ERC20(wethAddress),
        max_fill_amount
    );
    IERC20(buy_gem).safeTransfer(msg.sender, fill);

    uint256 _after = ERC20(_weth).balanceOf(address(this));
    uint256 delta = _after - _before;

    // Return unspent coins to sender
    if (delta > 0) {
        IWETH(wethAddress).withdraw(delta);
        // msg.sender.transfer(delta);
        (bool success, ) = msg.sender.call{value: delta}("");
        require(success, "Transfer failed.");
    }
}
```

As we can see in the previous snippet, the function will potentially refund the caller the unspent ETH in lines 412-417. If this call is being wrapped using the `FeeWrapper`, then `msg.sender` will be the `FeeWrapper` contract.

## Proof of Concept

In the following test, we create a demonstration contract `FeeWrapperTarget` which includes a function named `demoETH` that will refund half of the sent amount back to the caller. The wrapped call will fail, as the `FeeWrapperTarget` will try to refund the ETH to the `FeeWrapper` contract which doesn’t allow ETH payments, causing the whole transaction to be reverted.

_Note: the snippet shows only the relevant code for the test. Full test file can be found[here](https://gist.github.com/romeroadrian/f3b7d6f9ab043340de7deb67a9c515e5)._
```solidity
function test_FeeWrapper_FailsWithETHRefund() public {
    FeeWrapperTarget target = new FeeWrapperTarget(ERC20(address(0)));

    uint256 amount = 1 ether;
    uint256 fee = 0.1 ether;

    vm.deal(alice, amount + fee);

    // Alice will call demoERC20
    vm.startPrank(alice);

    FeeWrapper.CallParams memory callParams;
    callParams.selector = FeeWrapperTarget.demoETH.selector;
    callParams.args = "";
    callParams.target = address(target);
    callParams.feeParams.feeToken = address(0);
    callParams.feeParams.totalAmount = amount + fee;
    callParams.feeParams.feeAmount = fee;
    callParams.feeParams.feeTo = makeAddr("FeeRecipient");

    // The following call will fail, the FeeWrapper contract is not prepared to receive the ETH from the target contract
    vm.expectRevert("low-level call to the router failed");
    feeWrapper.rubicall{value: amount + fee}(callParams);

    vm.stopPrank();
}
```

## Recommendation

Allow the `FeeWrapper` contract to receive ETH by implementing the `receive` function. After the call to the target contract, refund any ETH amount present in the `FeeWrapper` contract back to the original caller.

Core issue is that the `FeeWrapper` lacks functionality to handle refunds in general, whether in ETH or ERC20. Specifically, for ETH, lacking `receive()` / `fallback()` functions to accept inbound transfers.

Generally, I would’ve considered this to be Medium severity because it’s conditional on the target contract sending back funds. However, the `FeeWrapper` is expected to interact with the Rubicon contracts, which the warden has shown to have the ability send back funds. Hence, the High severity is justified.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The FeeWrapper contract is designed to wrap arbitrary calls that include an ETH payment. Inside its internal routine it first deducts a fee and then forwards the remaining ETH to the target contract using a low‑level call. The problem arises when the target contract, as part of its normal logic, sends back a portion of the ETH it received – for example to refund unspent funds. Because FeeWrapper does not implement a receive() or payable fallback function, it is unable to accept the inbound ETH transfer. The refund attempt therefore fails, the low‑level call returns false, and the wrapper reverts with the generic error "low‑level call to the router failed". From a user perspective the transaction appears to revert unexpectedly; the user expects a refund or at least a successful execution, but instead sees a failure and a zero balance change, leading to confusion. The issue only manifests when the wrapped target contract includes a refund path; calls that consume the full forwarded amount succeed, making the bug easy to miss during casual testing. All users who rely on FeeWrapper to interact with contracts that may return ETH – such as RubiconRouter’s buyAllAmountWithETH function which withdraws unspent WETH and attempts to send it back to msg.sender – are affected. The audit discovered the flaw by deploying a simple test contract that refunds half of the sent ETH; the wrapped call reverted, confirming the missing payable fallback. The vulnerability is a classic case of improper handling of inbound ETH refunds, a subclass of missing receive/fallback bugs that break accounting assumptions about net balances. Although no funds are permanently lost because the transaction reverts, the bug prevents legitimate use cases and can cause users to think their funds disappeared. The recommended remediation is to add a receive() (or payable fallback) to FeeWrapper so it can accept ETH refunds, and after the wrapped call to forward any residual balance back to the original caller, thereby restoring the expected accounting flow.
