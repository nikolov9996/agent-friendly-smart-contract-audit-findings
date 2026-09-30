---
id: 18589
severity: "High"
---

# Lack of a return value handing in `ArbitrumBranchBridgeAgent._performCall`

## Description

In `ArbitrumBranchBridgeAgent`, the `_performCall()` is overridden to directly call `RootBridgeAgent.anyExecute()` instead of performing an `AnyCall` cross-chain transaction, as `RootBridgeAgent` is also in Arbitrum. However, unlike `AnyCall`, `ArbitrumBranchBridgeAgent._performCall()` is missing the handling of a return value for `anyExecute()`.

```solidity
function _performCall(bytes memory _callData) internal override {
    IRootBridgeAgent(rootBridgeAgentAddress).anyExecute(_callData);
}
```

That is undesirable, as `RootBridgeAgent.anyExecute()` has a try/catch that prevents the revert from bubbling up. Instead, it expects `ArbitrumBranchBridgeAgent._performCall()` to revert when `success == false`, which is currently missing.

```solidity
try RootBridgeAgentExecutor(bridgeAgentExecutorAddress).executeSignedWithDeposit(
    address(userAccount), localRouterAddress, data, fromChainId
) returns (bool, bytes memory res) {
    (success, result) = (true, res);
} catch (bytes memory reason) {
    result = reason;
}
```

## Proof of Concept

Add the following `MockContract` and test case to `ArbitrumBranchTest.t.sol` and run the test case:

```solidity
contract MockContract is Test {
    function test() external {
        require(false);
    }
} 

function testPeakboltArbCallOutWithDeposit() public {
    //Set up
    testAddLocalTokenArbitrum();

    // deploy mock contract to call using multicall
    MockContract mockContract = new MockContract();

    //Prepare data
    address outputToken;
    uint256 amountOut;
    uint256 depositOut;
    bytes memory packedData;

    {
        outputToken = newArbitrumAssetGlobalAddress;
        amountOut = 100 ether;
        depositOut = 50 ether;

        Multicall2.Call[] memory calls = new Multicall2.Call[](1);

        //prepare for a call to MockContract.test(), which will revert
        calls[0] = Multicall2.Call({target: address(mockContract), callData: abi.encodeWithSignature("test()")});
    
        //Output Params
        OutputParams memory outputParams = OutputParams(address(this), outputToken, amountOut, depositOut);

        //toChain
        uint24 toChain = rootChainId;

        //RLP Encode Calldata
        bytes memory data = abi.encode(calls, outputParams, toChain);

        //Pack FuncId
        packedData = abi.encodePacked(bytes1(0x02), data);
    }

    //Get some gas.
    hevm.deal(address(this), 1 ether);

    //Mint Underlying Token.
    arbitrumNativeToken.mint(address(this), 100 ether);

    //Approve spend by router
    arbitrumNativeToken.approve(address(localPortAddress), 100 ether);

    //Prepare deposit info
    DepositInput memory depositInput = DepositInput({
        hToken: address(newArbitrumAssetGlobalAddress),
        token: address(arbitrumNativeToken),
        amount: 100 ether,
        deposit: 100 ether,
        toChain: rootChainId
    });

    //Mock messaging layer fees
    hevm.mockCall(
        address(localAnyCongfig),
        abi.encodeWithSignature("calcSrcFees(address,uint256,uint256)", address(0), 0, 100),
        abi.encode(0)
    );

    console2.log("Initial User Balance: %d", arbitrumNativeToken.balanceOf(address(this)));

    //Call Deposit function
    arbitrumMulticallBridgeAgent.callOutSignedAndBridge{value: 1 ether}(packedData, depositInput, 0.5 ether);

    // This shows that deposit entry is successfully created
    testCreateDepositSingle(
        arbitrumMulticallBridgeAgent,
        uint32(1),
        address(this),
        address(newArbitrumAssetGlobalAddress),
        address(arbitrumNativeToken),
        100 ether,
        100 ether,
        1 ether,
        0.5 ether
    );

    // The following shows that the user deposited to the LocalPort, but it is not deposited/bridged to the user account
    console2.log("LocalPort Balance (expected):", uint256(50 ether));
    console2.log("LocalPort Balance (actual):", MockERC20(arbitrumNativeToken).balanceOf(address(localPortAddress)));
    //require(MockERC20(arbitrumNativeToken).balanceOf(address(localPortAddress)) == 50 ether, "LocalPort should have 50 tokens");

    console2.log("User Balance: (expected)", uint256(50 ether));
    console2.log("User Balance: (actual)", MockERC20(arbitrumNativeToken).balanceOf(address(this)));
    //require(MockERC20(arbitrumNativeToken).balanceOf(address(this)) == 50 ether, "User should have 50 tokens");

    console2.log("User Global Balance: (expected)", uint256(50 ether));
    console2.log("User Global Balance: (actual)", MockERC20(newArbitrumAssetGlobalAddress).balanceOf(address(this)));
    //require(MockERC20(newArbitrumAssetGlobalAddress).balanceOf(address(this)) == 50 ether, "User should have 50 global tokens");

    // retryDeposit() will fail as well as the transaction is marked executed in executionHistory
    uint32 depositNonce = arbitrumMulticallBridgeAgent.depositNonce() - 1;
    hevm.deal(address(this), 1 ether);
    //hevm.expectRevert(abi.encodeWithSignature("GasErrorOrRepeatedTx()"));
    arbitrumMulticallBridgeAgent.retryDeposit{value: 1 ether}(true, depositNonce, "", 0.5 ether, rootChainId);
}
```

## Recommendation

Handle the return value of `anyExecute()` in `_performCall()` and revert on `success == false`.

Addressed [here](https://github.com/Maia-DAO/eco-c4-contest/tree/266).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the ArbitrumBranchBridgeAgent contract where the internal function _performCall is overridden to invoke RootBridgeAgent.anyExecute directly, but it does not inspect the boolean success flag returned by anyExecute. In the original AnyCall design the caller checks the returned success value and reverts when the cross‑chain execution fails. RootBridgeAgent.anyExecute, however, wraps the external call in a try/catch block and returns false when the called contract reverts, while swallowing the original revert reason. Because _performCall ignores this return value, a failure inside anyExecute is silently treated as a successful bridge operation. This omission allows a situation where a user deposits tokens to the bridge, the underlying call to the destination contract reverts (as demonstrated by the MockContract test that deliberately throws), yet the bridge transaction does not revert. The protocol records the deposit as executed, the local port holds the tokens, and the user’s balance on both the source and destination chains remains unchanged. From the user’s perspective the expected outcome – receipt of the bridged tokens – does not occur; the UI may show a successful transaction hash while the token balance stays at zero or at the pre‑deposit amount, leading to confusion and apparent loss of funds. The bug is a classic case of unchecked external call return values, where error propagation is missing. It was discovered during a Code4rena audit by adding a mock contract that forces a revert and observing that the bridge reports success while the funds are not transferred. The issue is hard to notice because no explicit revert is emitted, transaction receipts appear normal, and the only symptom is a mismatch between expected and actual token balances. The impact is high: users may lose access to deposited assets, the protocol’s accounting becomes inconsistent, and retry mechanisms fail because the execution history marks the deposit as already processed. The proper fix is to capture the (bool success, bytes memory result) returned by anyExecute (or the underlying executor) inside _performCall and to revert the transaction when success is false, thereby propagating the error to the caller and ensuring that failed cross‑chain calls do not falsely appear successful.
