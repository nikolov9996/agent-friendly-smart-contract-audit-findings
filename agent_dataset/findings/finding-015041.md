---
id: 15041
severity: "High"
---

# Many 0x transformations ignore outputToken, returning unaccounted for tokens to account and risking liquidations

## Description

When we call `transformERC20()` on the 0x contract, the following inputs are included as arguments:
```solidity
function transformERC20(
    address inputToken,
    address outputToken,
    uint256 inputTokenAmount,
    uint256 minOutputTokenAmount,
    Transformation[] calldata transformations
) external payable returns (uint256 outputTokenAmount);
```
`TransformController.sol` assumes that `outputToken` will be the only token returned.

However, if we look at the implementation of the function on 0x, we see the following flow:
all tokens are transferred into the `state.wallet` contract
we execute all the transformations based on our specified parameters
after the transformations, if the `state.wallet` has any of our output token, it is transferred back to us
we ensure that our balance of `outputToken` has increased by at least `minOutputTokenAmount`

If we look at the specific transformer implementations, we can see that they take their data from the `transformations` params and do not have visibility into the `inputToken` or `outputToken`. In addition, many of them transfer the assets directly back to the caller, rather than to the `state.wallet` contract.

As a few examples:
[PositiveSlippageFeeTransformer.sol](https://github.com/0xProject/protocol/blob/198d986fdc8c65eb7de718dbc277c097cd7a53b7/contracts/zero-ex/contracts/src/transformers/PositiveSlippageFeeTransformer.sol) allows you to send a token, an amount and a recipient, and it will send any balance it holds over the amount to that recipient.
[PayTakerTransformer.sol](https://github.com/0xProject/protocol/blob/198d986fdc8c65eb7de718dbc277c097cd7a53b7/contracts/zero-ex/contracts/src/transformers/PayTakerTransformer.sol) allows you to specify a list of tokens and amounts, and it will send that amount of each token to the `msg.sender` of the original call.
[AffiliateFeeTransformer.sol](https://github.com/0xProject/protocol/blob/198d986fdc8c65eb7de718dbc277c097cd7a53b7/contracts/zero-ex/contracts/src/transformers/AffiliateFeeTransformer.sol) takes a list of tokens, amounts and recipients and sends the specified amount of each token to the matching recipient.

In each of these cases, there will be no assets sent back to the `state.wallet` contract.

However, the `transformERC20()` function still checks that our balance of the `outputToken` has increased by at least `minOutputTokenAmount`. However, it is highly possible that other transformations will have caused this increase, or that a user will input `0` for this parameter since it often doesn't matter.

The result is that if a user uses has a token returned by one of these transformers that is not the `outputToken`, it will not be accounted for by Sentiment and will not count towards their account balance. This could result in unfair liquidations, as the user's balance will be lower than it should be.

## Proof of Concept

Here is a test that can be dropped into `0xTransform.t.sol` to demonstrate this issue.

First, add the `IERC20Token` interface to the top of the test file:
```solidity
interface IERC20Token {
    function balanceOf(address) external returns(uint);
}
```
Then, add the `TransformData` struct (used by PayTakerTransformer) to the contract:
```solidity
struct TransformData {
    // The tokens to transfer to the taker.
    IERC20Token[] tokens;
    // Amount of each token in `tokens` to transfer to the taker.
    // `uint(-1)` will transfer the entire balance.
    uint256[] amounts;
}
```
Finally, run the following test to show that the controller returns no tokens in, but the 0x contract returns WETH (not the `outputToken`) to the user:
```solidity
function testMissesOutputTokenInSomeTransformers() public {
    address SENTIMENT_WALLET = address(1234);
    IERC20Token weth = IERC20Token(0x82aF49447D8a07e3bd95BD0d56f35241523fBab1);
    address zeroex = 0xDef1C0ded9bec7F1a1670819833240f027b25EfF;

    // first, we set up the data for the transformation
    IERC20Token[] memory tokens = new IERC20Token[](1);
    tokens[0] = weth;
    uint256[] memory amounts = new uint256[](1);
    amounts[0] = 100 ether;
    TransformData memory transformData = TransformData(tokens, amounts);
    ITransformERC20Feature.Transformation[] memory transformations = new ITransformERC20Feature.Transformation[](1);
    transformations[0] = ITransformERC20Feature.Transformation(16, abi.encode(transformData));

    // now we create the data for the call, which we'll use with the controller and the forked 0x contract
    bytes memory data = abi.encodeWithSelector(
        ITransformERC20Feature.transformERC20.selector, ETH, ETH, 0, 0, transformations
    );

    // the controller says there are no tokens in
    (bool canCall, address[] memory tokensIn, address[] memory tokensOut) =
        controllerFacade.canCall(target, true, data);

    assert(tokensIn.length == 0);

    // create a fork and seed the 0x contract with some leftover weth to take
    vm.createSelectFork("INSERT RPC URL");
    deal(address(weth), 0xdB6f1920A889355780aF7570773609Bd8Cb1f498, 100 ether);

    // in reality, we can move our weth balance from zero to non-zero
    assert(weth.balanceOf(SENTIMENT_WALLET) == 0);
    vm.prank(SENTIMENT_WALLET);
    zeroex.call(data);
    assert(weth.balanceOf(SENTIMENT_WALLET) > 0);
}
```

## Recommendation

If you want to interact with 0x without risk, you'll need to get more granular on which transformers are accepted.

This will accomplish two things:

1) You can decode the data passed to the transformer to ensure that all returned tokens are accounted for.

2) By default, you will not support new transformers, which will ensure that you are able to safely add new transformer support, rather than risking being surprised later.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way Sentiment’s TransformController interacts with the 0x transformERC20 function. The controller assumes that the only token that will be returned after a series of transformations is the explicit outputToken supplied to the call, and it validates the result solely by checking that the caller’s balance of that token has increased by at least minOutputTokenAmount. In reality, many 0x transformers (for example PositiveSlippageFeeTransformer, PayTakerTransformer and AffiliateFeeTransformer) are written without any awareness of the inputToken or outputToken parameters. Instead of sending any acquired assets back to the temporary state.wallet contract, they forward tokens directly to the original caller (msg.sender). Consequently, when such a transformer is included in the transformations array, tokens other than the declared outputToken can be transferred to the user’s address, while the state.wallet never receives them. The controller’s post‑call accounting therefore records zero tokensIn and zero tokensOut, because it only inspects the balance change of the expected outputToken. This mismatch means that a user may actually receive a token (e.g., WETH) that is not reflected in the protocol’s accounting, leading to an understated collateral balance. Under normal operation the user expects to receive only the outputToken; instead they see an unexpected token appear in their wallet, yet the protocol still believes their balance is lower than it truly is. When the risk engine later evaluates the user’s position, it may trigger a liquidation despite the hidden token that could have prevented it. The issue is most likely to be triggered when the caller sets minOutputTokenAmount to zero or a very low value, or when the transformation list includes any of the aforementioned fee‑or‑slippage transformers that send assets directly to the caller. The bug was uncovered during a security audit by constructing a test that calls transformERC20 with a PayTakerTransformer that returns WETH; the controller reported no output tokens while the wallet’s WETH balance increased. The problem is subtle because the expected outputToken balance does change as required, so a superficial check passes, and the extra token may be overlooked in UI displays that only show the primary asset. This class of flaw can be described as improper accounting of external token transfers or unchecked return values in composable DeFi pipelines. To remediate, the controller should either restrict the set of allowed transformers to those that reliably route all assets through the state.wallet, or it must decode each transformer’s calldata and explicitly verify that any token transferred out is captured and recorded in the tokenIn/tokenOut arrays. In addition, the post‑call validation should be extended to ensure that the total value of all tokens received meets the intended minimum, not just the balance of a single outputToken. Implementing these safeguards will prevent hidden token flows, preserve accurate collateral accounting, and eliminate the risk of unfair liquidations.
