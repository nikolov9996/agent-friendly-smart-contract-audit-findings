---
id: 19091
severity: "High"
---

# `BalancerStrategy.sol`: `_withdraw` withdraws insufficient tokens

## Description

The function `_withdraw` in the balancer strategy contract is called during withdraw operations to withdraw WETH from the balancer pool. The function calculates the amount to withdraw, and then calls `_vaultWithdraw` function.

```solidity
if (amount > queued) {
    uint256 pricePerShare = pool.getRate();
    uint256 decimals = IStrictERC20(address(pool)).decimals();
    uint256 toWithdraw = (((amount - queued) * (10 ** decimals)) /
        pricePerShare);

    _vaultWithdraw(toWithdraw);
}
```

The function `_vaultWithdraw` submits an exit request with the following userData.

```solidity
exitRequest.userData = abi.encode(
    2,
    exitRequest.minAmountsOut,
    pool.balanceOf(address(this))
);
```

A value of 2 here corresponds to specifying the exact number of tokens coming out of the contract. Thus the function `_vaultWithdraw` will withdraw the exact number of tokens passed to it in its parameter.

The issue however is that the function `_vaultWithdraw` is not called with the amount of tokens needed to be withdrawn, it is called by the amount scaled down by `pricePerShare`. Thus if the actual withdrawn amount is less the amounts the user actually wanted. This causes a revert in the next step.

```solidity
require(
    amount <= wrappedNative.balanceOf(address(this)),
    "BalancerStrategy: not enough"
);
```

Since an insufficient amount of tokens are withdrawn, this step will revert if there arent enough spare tokens in the contract. Since the contract incorrectly scales down the withdraw amount and causes a revert, this is classified as a high severity issue.

## Proof of Concept

The following exercise shows that passing the same `exitRequest` data to the balancerPool actually extracts the exact number of tokens as specified in `minamountsOut`.

A position is created on optimism’s weth-reth pool. The `userData` is generated using the following code.

```solidity
function temp() external pure returns(bytes memory){
    uint256[] memory amts = new uint256[](2);
    amts[0] = 500;
    amts[1] = 0;
    uint256 max = 20170422329691;
    return(abi.encode(2,amts,max));
}
```

Min amount out of WETH is set to 500 wei. The `exitRequest`is then constructed as follows with the userData from above.

```json
{
    "assets": [
        "0x4200000000000000000000000000000000000006",
        "0x9bcef72be871e61ed4fbbc7630889bee758eb81d"
    ],
    "minAmountsOut": ["500", "0"],
    "toInternalBalance": false,
    "userData": "0x00000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000060000000000000000000000000000000000000000000000000000012584adba15b000000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000001f40000000000000000000000000000000000000000000000000000000000000000"
}
```

This is an exit request of type 2, which specifies the exact amount of tokens to be withdrawn. This transaction was then run on tenderly to check how many tokens are withdrawn. From the screenshot [here](https://gist.github.com/carrotsmuggler/707aa76f78028d6fc66d5ba630d8d677) from tenderly we can see only 500 wei of WETH is withdrawn.

This proves that the `_vaultWithdraw` function withdraws the exact amount of tokens passed to it as a parameter. Since the passed parameter is scaled down by `pricePerShare`, this leads to an insufficient amount withdrawn, and eventually a revert.

## Recommendation

Pass the amount to be withdrawn without scaling it down by `pricePerShare`.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the withdraw path of the BalancerStrategy contract. When a user initiates a withdrawal, the internal function _withdraw computes the amount of WETH that must be taken from the Balancer pool. The calculation first determines the shortfall amount - queued and then divides this value by the pool's pricePerShare, effectively scaling the required token amount down to a share‑based figure. The resulting toWithdraw value is passed to _vaultWithdraw, which builds an exit request of type 2. In Balancer, a type 2 exit request instructs the vault to return exactly the number of tokens specified in the request. Consequently, the vault transfers only the scaled‑down toWithdraw amount, which is smaller than the original user‑requested amount. After the vault call the strategy checks that the contract’s WETH balance covers the full amount with require(amount <= wrappedNative.balanceOf(address(this)), "BalancerStrategy: not enough"). Because the previous step delivered fewer tokens, the balance check fails and the transaction reverts. The bug manifests whenever the requested withdrawal exceeds the amount already queued, i.e., when amount > queued. It affects any user attempting to withdraw more than the queued portion, the protocol’s accounting logic, and ultimately the funds that should be returned to the user. The issue was discovered during a Code4rena audit by inspecting the arithmetic in _withdraw and confirming through a proof‑of‑concept that the vault returns exactly the number encoded in userData. The problem is subtle because the contract appears to call the correct internal function and the scaling operation looks reasonable, yet the mismatch between share‑based scaling and exact token withdrawal is not obvious from the UI; users see a revert and may think the contract is malicious or broken, while the balance on the contract may temporarily show a shortfall. This is an accounting‑logic bug where the contract under‑withdraws tokens, violating the invariant that the contract must hold at least the amount promised to the user. The appropriate fix is to pass the original amount - queued (or the full amount) directly to _vaultWithdraw without dividing by pricePerShare, or to adjust the exit request to request the correct number of shares instead of exact tokens. By aligning the withdrawal request with the intended token amount, the contract will satisfy the balance check and prevent unexpected reverts, restoring correct fund flow and user confidence.
