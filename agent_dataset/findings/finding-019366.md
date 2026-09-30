---
id: 19366
severity: "High"
---

# Loss of user funds, as LeverageMacroReferences can’t do an arbitrary system call to the function claimsSurplusCollShare in order to claim the extra surplus collateral gained from their liquidated or fully redeemed Cdps

## Description

On a short explanation, leverage macros are contracts specifically made to interact with the eBTC system, with a leverage macro you can:

  * Open, adjust and close Cdps
  * Take eBTC, stETH flashloans
  * Make swaps in DEXes
  * Do arbitrary calls

Everyone is free to make a call to one of the functions in LeverageMacroFactory and deploy a new copy of the reference implementation of LeverageMacro for self use.

```solidity
        /// @notice Deploys a new macro for you
        function deployNewMacro() external returns (address) {
            return deployNewMacro(msg.sender);
        }

        /// @notice Deploys a new macro for an owner, only they can operate the macro
        function deployNewMacro(address _owner) public returns (address) {
            address addy = address(
                new LeverageMacroReference(
                    borrowerOperations,
                    activePool,
                    cdpManager,
                    ebtcToken,
                    stETH,
                    sortedCdps,
                    _owner
                )
            );

            emit DeployNewMacro(_owner, addy);

            return addy;
        }
```

While having an opened Cdp position, there is always a chance for your position to be fully redeemed or liquidated. In this two cases there will always be a surplus collateral left to the owner of the Cdp when:

  * A Cdp with ICR >= MCR is fully redeemed.
  * A Cdp with ICR > MCR is fully liquidated in recovery mode.

Any surplus collateral is send to the CollSurplusPool, which can later be claimed by the owner of the Cdp. The only way for an owner to claim his surplus collateral is to call the function claimSurplusCollShares in borrowerOperations, which is the only entry point to the CollSurplusPool.

```solidity
        /// @notice Claim remaining collateral from a redemption or from a liquidation with ICR > MCR in Recovery Mode
        /// @notice when a Cdp has been fully redeemed from and closed, or liquidated in Recovery Mode with a collateralization ratio higher enough (like over MCR)
        /// @notice the borrower is allowed to claim their stETH collateral surplus that remains in the system if any
        function claimSurplusCollShares() external override {
            // send ETH from CollSurplus Pool to owner
            collSurplusPool.claimSurplusCollShares(msg.sender);
        }
```

The problem here is that LeverageMacroReferences don’t have build in feature to claim the surplus collateral from its fully redeemed or liquidated Cdps. In this case the only way for LeverageMacroReference to claim the surplus collateral is to make an arbitrary call to the function claimSurplusCollShares in borrowerOperations. However this isn’t possible as the LeverageMacroReference ensures there aren’t any arbitrary calls made to the system contracts.

As we can see In _doSwap the first thing the function does, is to call the internal function _ensureNotSystem which ensures that the arbitraty call isn’t made to any of the system contracts. Duo to that the function _doSwap will revert when a LeverageMacroReference tries to make an arbitrary call to borrowerOperations.

```solidity
        /// @dev Prevents doing arbitrary calls to protected targets
        function _ensureNotSystem(address addy) internal {
            /// @audit Check and add more if you think it's better
            require(addy != address(borrowerOperations));
            require(addy != address(sortedCdps));
            require(addy != address(activePool));
            require(addy != address(cdpManager));
            require(addy != address(this)); // If it could call this it could fake the forwarded caller
        }

        function _doSwap(SwapOperation memory swapData) internal {
            // Ensure call is safe
            // Block all system contracts
            _ensureNotSystem(swapData.addressForSwap);

            // Exact approve
            // Approve can be given anywhere because this is a router, and after call we will delete all approvals
            IERC20(swapData.tokenForSwap).safeApprove(
                swapData.addressForApprove,
                swapData.exactApproveAmount
            );

            // Call and perform swap
            // NOTE: Technically approval may be different from target, something to keep in mind
            // Call target are limited
            // But technically you could approve w/e you want here, this is fine because the contract is a router and will not hold user funds
            (bool success, ) = excessivelySafeCall(
                swapData.addressForSwap,
                gasleft(),
                0,
                0,
                swapData.calldataForSwap
            );
            require(success, "Call has failed");

            // Approve back to 0
            // Enforce exact approval
            // Can use max because the tokens are OZ
            // val -> 0 -> 0 -> val means this is safe to repeat since even if full approve is unused, we always go back to 0 after
            IERC20(swapData.tokenForSwap).safeApprove(swapData.addressForApprove, 0);

            // Do the balance checks after the call to the aggregator
            _doSwapChecks(swapData.swapChecks);
        }
```

Since there is no built in feature to claim the surplus collateral and LeverageMacroReference can’t make an arbitrary call to borrowerOperations. Any surplus collateral owned by LeverageMacroReference can’t be further claimed back and will be permanently stuck in CollSurplusPool.

## Proof of Concept

POC steps in the function testLeverageIssue:
    - Step 1: Get the macro's owner and check if the owner is the wallet address.
    - Step 2: Get data for the function doOperation.
    - Step 3: Approve leverage with the Cdps's collateral + liquidator rewards.
    - Step 4: Call the function doOperation twice and open two Cdps.
    - Step 5: Check one of the Cdps was opened && the macro address is the Cdp owner.
    - Step 6: The macro reference always sweeps back to the wallet, but make sure that happens.
    - Step 7: Redeem fully back one of the Cdps to gain a surplus collateral in the surplus pool.
    - Step 8: Make sure the Cdp was fully redeemed.
    - Step 9: Check that the macro received surplus collateral from the redeeming.
    - Step 10: Preparing data for the swap and the arbitrary call.
    - Step 11: Do arbitrary call to the function claimSurplusCollShares in borrowerOperations.
    - Final: Expect revert as the leverage macro can't make arbitrary calls to the system contracts.

```solidity
    // SPDX-License-Identifier: UNLICENSED
    pragma solidity 0.8.17;

    import "forge-std/Test.sol";
    import {SimplifiedDiamondLike} from "../contracts/SimplifiedDiamondLike.sol";

    import {eBTCBaseInvariants} from "./BaseInvariants.sol";
    import {LeverageMacroReference} from "../contracts/LeverageMacroReference.sol";
    import {LeverageMacroBase} from "../contracts/LeverageMacroBase.sol";
    import {ICdpManagerData} from "../contracts/Interfaces/ICdpManagerData.sol";

    contract LeverageMacroReferenceIssue is eBTCBaseInvariants {

        address wallet = address(0xbad455);

        LeverageMacroReference macro_reference;
        LeverageMacroBase macro_base;

        function setUp() public override {
            super.setUp();

            connectCoreContracts();
            connectLQTYContractsToCore();

            // straight creating new macro reference for the test
            macro_reference = new LeverageMacroReference(
                address(borrowerOperations),
                address(activePool),
                address(cdpManager),
                address(eBTCToken),
                address(collateral),
                address(sortedCdps),
                wallet
            );

            dealCollateral(wallet, 100e18);
        }

        function testLeverageIssue() public {

            vm.startPrank(wallet);

            // Step 1: Get the macro's owner and check if the owner is the wallet address
            address macroOwner = macro_reference.owner();
            assert(wallet == macroOwner);

            // Step 2: Get data for the function doOperation
            LeverageMacroBase.SwapOperation[] memory _levSwapsBefore;
            LeverageMacroBase.SwapOperation[] memory _levSwapsAfter;

            uint256 netColl = 11e18;

            uint256 grossColl = netColl + cdpManager.LIQUIDATOR_REWARD();

            uint256 debt = _utils.calculateBorrowAmount(
                netColl,
                priceFeedMock.fetchPrice(),
                COLLATERAL_RATIO
            );

            LeverageMacroBase.OpenCdpOperation memory _opData = LeverageMacroBase.OpenCdpOperation(
                debt,
                bytes32(0),
                bytes32(0),
                grossColl
            );

            bytes memory _opDataEncoded = abi.encode(_opData);

            LeverageMacroBase.LeverageMacroOperation memory operation = LeverageMacroBase
                .LeverageMacroOperation(
                    address(collateral),
                    (grossColl - 0),
                    _levSwapsBefore,
                    _levSwapsAfter,
                    LeverageMacroBase.OperationType.OpenCdpOperation,
                    _opDataEncoded
                );

            LeverageMacroBase.PostCheckParams memory postCheckParams = LeverageMacroBase
                .PostCheckParams({
                    expectedDebt: LeverageMacroBase.CheckValueAndType({
                        value: 0,
                        operator: LeverageMacroBase.Operator.skip
                    }),
                    expectedCollateral: LeverageMacroBase.CheckValueAndType({
                        value: 0,
                        operator: LeverageMacroBase.Operator.skip
                    }),
                    cdpId: bytes32(0),
                    expectedStatus: ICdpManagerData.Status.active
                });

            // Step 3: Approve leverage with the Cdps's collateral + liquidator rewards.
            collateral.approve(address(macro_reference), 22e18 + 4e17);

            // Step 4: Call the function doOperation twice and open two Cdps
            // Need more than one Cdp in the system to fully redeem a Cdp.
            macro_reference.doOperation(
                        LeverageMacroBase.FlashLoanType.noFlashloan,
                        0,
                        operation,
                        LeverageMacroBase.PostOperationCheck.openCdp,
                        postCheckParams
                    );

            macro_reference.doOperation(
                        LeverageMacroBase.FlashLoanType.noFlashloan,
                        0,
                        operation,
                        LeverageMacroBase.PostOperationCheck.openCdp,
                        postCheckParams
                    );

            // Step 5: Check one of the Cdps was opened && the macro address is the Cdp owner
            bytes32 cdpId = sortedCdps.cdpOfOwnerByIndex(address(macro_reference), 0);
            address cdpOwner = sortedCdps.getOwnerAddress(cdpId);
            assert(address(macro_reference) == cdpOwner);

            // Step 6: The macro reference always sweeps back to the wallet, but make sure that happens
            uint256 balance = eBTCToken.balanceOf(wallet);
            assert(balance == (debt * 2)); // The debt of the 2 Cdps opened

            // Step 7: Redeem fully back one of the Cdps to gain a surplus collateral in the surplus pool
            cdpManager.redeemCollateral(debt, cdpId, bytes32(0), bytes32(0), 0, 0, 1e18);

            // Step 8: Make sure the Cdp was fully redeemed
            bool redeemed = sortedCdps.contains(cdpId); // False means its not in the list == redeemed
            assert(redeemed == false);

            // Step 9: Check that the macro received surplus collateral from the redeeming
            uint256 surplusColl = collSurplusPool.getSurplusCollShares(address(macro_reference));
            assert(surplusColl > 0);

            // Step 10: Preparing data for the swap and the arbitrary call.
            LeverageMacroBase.SwapCheck[] memory _swapChecks = new LeverageMacroBase.SwapCheck[](1);
            _swapChecks[0] = LeverageMacroBase.SwapCheck(address(0), 0); // empty

            LeverageMacroBase.SwapOperation memory swap = LeverageMacroBase.SwapOperation(
                address(0),
                address(0),
                0,
                address(borrowerOperations),
                abi.encodeCall(borrowerOperations.claimSurplusCollShares, ()),
                _swapChecks
            );

            // Step 11: Do arbitrary call to the function claimSurplusCollShares in borrowerOperations
            // Expect revert as the macro ensures there aren't calls to the system contracts
            // Macro isn't able to call borrowerOperations, check the function _ensureNotSystem.
            vm.expectRevert();
            _doSwap(swap);

            vm.stopPrank();
        }

        // Removing everything else expect the _ensureNotSystem and the excessivelySafeCall function
        // (don't need the other parts for the issue showcase)
        function _doSwap(LeverageMacroBase.SwapOperation memory swapData) internal {
            // Ensure call is safe
            // Block all system contracts
            _ensureNotSystem(swapData.addressForSwap);

            // Call and perform swap
            // NOTE: Technically approval may be different from target, something to keep in mind
            // Call target are limited
            // But technically you could approve w/e you want here, this is fine because the contract is a router and will not hold user funds
            (bool success, ) = excessivelySafeCall(
                swapData.addressForSwap,
                gasleft(),
                0,
                0,
                swapData.calldataForSwap
            );
            require(success, "Call has failed");
        }

        function excessivelySafeCall(
            address _target,
            uint256 _gas,
            uint256 _value,
            uint16 _maxCopy,
            bytes memory _calldata
        ) internal returns (bool, bytes memory) {
            // set up for assembly call
            uint256 _toCopy;
            bool _success;
            bytes memory _returnData = new bytes(_maxCopy);
            // dispatch message to recipient
            // by assembly calling "handle" function
            // we call via assembly to avoid memcopying a very large returndata
            // returned by a malicious contract
            assembly {
                _success := call(
                    _gas, // gas
                    _target, // recipient
                    _value, // ether value
                    add(_calldata, 0x20), // inloc
                    mload(_calldata), // inlen
                    0, // outloc
                    0 // outlen
                )
                // limit our copy to 256 bytes
                _toCopy := returndatasize()
                if gt(_toCopy, _maxCopy) {
                    _toCopy := _maxCopy
                }
                // Store the length of the copied bytes
                mstore(_returnData, _toCopy)
                // copy the bytes from returndata[0:_toCopy]
                returndatacopy(add(_returnData, 0x20), 0, _toCopy)
            }
            return (_success, _returnData);
        }

        /// @dev Prevents doing arbitrary calls to protected targets
        function _ensureNotSystem(address addy) internal {
            require(addy != address(borrowerOperations));
            require(addy != address(sortedCdps));
            require(addy != address(activePool));
            require(addy != address(cdpManager));
            require(addy != address(this));
        }
    }
```

## Recommendation

Allowing LeverageMacroReference to do an arbitrary call to one of the system contracts brings bigger risk. So I would say the best recommendation is to build a feature for the LeverageMacroReference to do a claim surplus operation in order to claim its surplus collateral from CollSurplusPool:

  * Adjust the enum to have a claim surplus operations as well

```solidity
        enum OperationType {
            OpenCdpOperation,
            AdjustCdpOperation,
            CloseCdpOperation,
            ClaimSurplusOperation 
        }
```

  * Add a new else if statement which is triggered when the operation is ClaimSurplusOperation, in the statement the new internal function _claimSurplusCallback is called.

```solidity
        function _handleOperation(LeverageMacroOperation memory operation) internal {
            uint256 beforeSwapsLength = operation.swapsBefore.length;
            if (beforeSwapsLength > 0) {
                _doSwaps(operation.swapsBefore);
            }

            // Based on the type we do stuff
            if (operation.operationType == OperationType.OpenCdpOperation) {
                _openCdpCallback(operation.OperationData);
            } else if (operation.operationType == OperationType.CloseCdpOperation) {
                _closeCdpCallback(operation.OperationData);
            } else if (operation.operationType == OperationType.AdjustCdpOperation) {
                _adjustCdpCallback(operation.OperationData);
            } else if (operation.operationType == OperationType.ClaimSurplusOperation) {
               _claimSurplusCallback();
            }

            uint256 afterSwapsLength = operation.swapsAfter.length;
            if (afterSwapsLength > 0) {
                _doSwaps(operation.swapsAfter);
            }
        }
```

  * Create the new internal function _claimSurplusCallback, which makes a call to the function claimSurplusCollShares in borrowerOperations and claims the leverage macro’s surplus collateral from CollSurplusPool.

```solidity
        function _claimSurplusCallback() internal {
            borrowerOperations.claimSurplusCollShares();
        }
```

  * After the recommendation LeverageMacroReferences are able to claim the surplus collateral of their fully redeemed or liquidated Cdps and everyone should be happy.

The finding is valid in that you cannot claim the surplus.

You could argue it requires being redeemed or liquidated, but I don’t think that can be considered an external requirement since it’s a normal behaviour.

Meet high: Assets can be stolen/lost/compromised directly (or indirectly if there is a valid attack path that does not have hand-wavy hypotheticals).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the LeverageMacroReference contract, which is designed to interact with the eBTC system but deliberately blocks any arbitrary external calls to core system contracts through the internal _ensureNotSystem check. When a CDP owned by a LeverageMacroReference is fully redeemed or liquidated with an ICR above the minimum collateralization ratio, the protocol deposits the excess collateral into the CollSurplusPool. The only legitimate way to retrieve that surplus is to invoke borrowerOperations.claimSurplusCollShares, which forwards the call to CollSurplusPool. Because LeverageMacroReference does not implement a dedicated claim‑surplus function and because its generic swap routine enforces _ensureNotSystem, any attempt to perform an arbitrary call to borrowerOperations is rejected, causing the transaction to revert. Consequently, the surplus collateral remains locked in CollSurplusPool forever, effectively disappearing from the user’s balance. This issue manifests only after a CDP has been fully redeemed or liquidated; during normal open, adjust, or close operations the macro works as expected, making the problem easy to overlook. Users of LeverageMacroReference see their expected refund or extra collateral turn into zero, while the protocol’s accounting shows the surplus still allocated but inaccessible, violating the business logic that surplus should be claimable by the CDP owner. The flaw was discovered during a security audit that exercised the full lifecycle of a CDP and observed a revert when the macro attempted the claim via its internal swap mechanism. The difficulty in spotting the bug stems from the fact that the macro’s primary functions operate correctly and the restriction is hidden behind a generic safety guard. The recommended remediation is to extend the macro’s operation enum with a ClaimSurplusOperation and implement an internal _claimSurplusCallback that safely calls borrowerOperations.claimSurplusCollShares, thereby providing a legitimate path for the macro to retrieve surplus collateral without breaching the system‑contract protection.
