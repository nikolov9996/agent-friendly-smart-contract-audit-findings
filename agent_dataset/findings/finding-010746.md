---
id: 10746
severity: "High"
---

# In `execute

## Description

[BridgeFacet.sol#L526-L616](https://github.com/code-423n4/2022-06-connext/blob/b4532655071566b33c41eac46e75be29b4a381ed/contracts/contracts/core/connext/facets/BridgeFacet.sol#L526-L616)  
[BridgeFacet.sol#L753-L803](https://github.com/code-423n4/2022-06-connext/blob/b4532655071566b33c41eac46e75be29b4a381ed/contracts/contracts/core/connext/facets/BridgeFacet.sol#L753-L803)  
[BridgeFacet.sol#L398-L428](https://github.com/code-423n4/2022-06-connext/blob/b4532655071566b33c41eac46e75be29b4a381ed/contracts/contracts/core/connext/facets/BridgeFacet.sol#L398-L428)  
[BridgeFacet.sol#L345-L351](https://github.com/code-423n4/2022-06-connext/blob/b4532655071566b33c41eac46e75be29b4a381ed/contracts/contracts/core/connext/facets/BridgeFacet.sol#L345-L351)  

Routers pay for transaction in destination domain then nomad messages come and routers get paid again. but the amount routers pay in `execute()` are what transaction sender signed and the amount routers receive is what nomad sends and handles in `_reconcile()` but this two amount can be different because of slippage and swap that happens in `xcall()` because the amount sent in nomad message is the result of `swapToLocalAssetIfNeeded()`.  
So it’s possible for routers to lose funds if some slippage happens in that swap.

## Proof of Concept

This is `xcall()` code:
```solidity
function xcall(XCallArgs calldata _args) external payable whenNotPaused nonReentrant returns (bytes32) {
  // Sanity checks.
  {
    // Correct origin domain.
    if (_args.params.originDomain != s.domain) {
      revert BridgeFacet__xcall_wrongDomain();
    }

    // Recipient is defined.
    if (_args.params.to == address(0)) {
      revert BridgeFacet__xcall_emptyTo();
    }

    // If callback address is not set, callback fee should be 0.
    if (_args.params.callback == address(0) && _args.params.callbackFee > 0) {
      revert BridgeFacet__xcall_nonZeroCallbackFeeForCallback();
    }

    // Callback is contract if supplied.
    if (_args.params.callback != address(0) && !Address.isContract(_args.params.callback)) {
      revert BridgeFacet__xcall_callbackNotAContract();
    }
  }

  bytes32 transferId;
  bytes memory message;
  XCalledEventArgs memory eventArgs;
  {
    // Get the remote BridgeRouter address; revert if not found.
    bytes32 remote = _mustHaveRemote(_args.params.destinationDomain);

    // Get the true transacting asset ID (using wrapper instead of native, if applicable).
    address transactingAssetId = _args.transactingAssetId == address(0)
      ? address(s.wrapper)
      : _args.transactingAssetId;

    // Check that the asset is supported -- can be either adopted or local.
    ConnextMessage.TokenId memory canonical = s.adoptedToCanonical[transactingAssetId];
    if (canonical.id == bytes32(0)) {
      // Here, the asset is *not* the adopted asset. The only other valid option
      // is for this asset to be the local asset (i.e. transferring madEth on optimism)
      // NOTE: it *cannot* be the canonical asset. the canonical asset is only used on
      // the canonical domain, where it is *also* the adopted asset.
      if (s.tokenRegistry.isLocalOrigin(transactingAssetId)) {
        // revert, using a token of local origin that is not registered as adopted
        revert BridgeFacet__xcall_notSupportedAsset();
      }

      (uint32 canonicalDomain, bytes32 canonicalId) = s.tokenRegistry.getTokenId(transactingAssetId);
      canonical = ConnextMessage.TokenId(canonicalDomain, canonicalId);
    }

    transferId = _getTransferId(_args, canonical);
    s.nonce += 1;

    // Store the relayer fee
    s.relayerFees[transferId] = _args.params.relayerFee;

    // Transfer funds of transacting asset to the contract from the user.
    // NOTE: Will wrap any native asset transferred to wrapped-native automatically.
    (, uint256 amount) = AssetLogic.handleIncomingAsset(
      _args.transactingAssetId,
      _args.amount,
      _args.params.relayerFee + _args.params.callbackFee
    );

    // Swap to the local asset from adopted if applicable.
    (uint256 bridgedAmt, address bridged) = AssetLogic.swapToLocalAssetIfNeeded(
      canonical,
      transactingAssetId,
      amount,
      _args.params.slippageTol
    );

    // Transfer callback fee to PromiseRouter if set
    if (_args.params.callbackFee != 0) {
      s.promiseRouter.initCallbackFee{value: _args.params.callbackFee}(transferId);
    }

    message = _formatMessage(_args, bridged, transferId, bridgedAmt);
    s.xAppConnectionManager.home().dispatch(_args.params.destinationDomain, remote, message);

    // Format arguments for XCalled event that will be emitted below.
    eventArgs = XCalledEventArgs({
      transactingAssetId: transactingAssetId,
      amount: amount,
      bridgedAmt: bridgedAmt,
      bridged: bridged
    });
  }

  // emit event
  emit XCalled(transferId, _args, eventArgs, s.nonce - 1, message, msg.sender);

  return transferId;
}
```

As you can see it swaps what user sent to `LoccalAsset` which the amount is `bridgedAmt` and then send value of `bridgedAmt` to nomad bridge `message = _formatMessage(_args, bridged, transferId, bridgedAmt)`.  
But the amount user signed in `_args.amount` is different and that what user sends to contract.  
The reasons that `bridgedAmt` could be different than `_args.amount` is:  
1- deflationary tokens in transferring from user.  
2- slippage in swap to local token.  
This is `_reconcile()` code:
```solidity
function _reconcile(uint32 _origin, bytes memory _message) internal {
  // Parse tokenId and action from the message.
  bytes29 msg_ = _message.ref(0).mustBeMessage();
  bytes29 tokenId = msg_.tokenId();
  bytes29 action = msg_.action();

  // Assert that the action is valid.
  if (!action.isTransfer()) {
    revert BridgeFacet__reconcile_invalidAction();
  }

  // Load the transferId.
  bytes32 transferId = action.transferId();

  // Ensure the transaction has not already been handled (i.e. previously reconciled).
  if (s.reconciledTransfers[transferId]) {
    revert BridgeFacet__reconcile_alreadyReconciled();
  }

  // NOTE: `tokenId` and `amount` must be in plaintext in the message so funds can *only* be minted by
  // `handle`. They are both used in the generation of the `transferId` so routers must provide them
  // correctly to be reimbursed.

  // Get the appropriate local token contract for the given tokenId on this chain.
  // NOTE: If the token is of remote origin and there is no existing representation token contract,
  // the TokenRegistry will deploy a new one.
  address token = s.tokenRegistry.ensureLocalToken(tokenId.domain(), tokenId.id());

  // Load amount once.
  uint256 amount = action.amnt();

  // Mint tokens if the asset is of remote origin (i.e. is representational).
  // NOTE: If the asset IS of local origin (meaning it's canonical), then the tokens will already be held
  // in escrow in this contract (from previous `xcall`s).
  if (!s.tokenRegistry.isLocalOrigin(token)) {
    IBridgeToken(token).mint(address(this), amount);

    // Update the recorded `detailsHash` for the token (name, symbol, decimals).
    // TODO: do we need to keep this
    bytes32 details = action.detailsHash();
    IBridgeToken(token).setDetailsHash(details);
  }

  // Mark the transfer as reconciled.
  s.reconciledTransfers[transferId] = true;

  // If the transfer was executed using fast-liquidity provided by routers, then this value would be set
  // to the participating routers.
  // NOTE: If the transfer was not executed using fast-liquidity, then the funds will be reserved for
  // execution (i.e. funds will be delivered to the transfer's recipient in a subsequent `execute` call).
  address[] memory routers = s.routedTransfers[transferId];

  // If fast transfer was made using portal liquidity, we need to repay
  // FIXME: routers can repay any-amount out-of-band using the `repayAavePortal` method
  // or by interacting with the aave contracts directly
  uint256 portalTransferAmount = s.portalDebt[transferId] + s.portalFeeDebt[transferId];

  uint256 toDistribute = amount;
  uint256 pathLen = routers.length;
  if (portalTransferAmount != 0) {
    // ensure a router took on credit risk
    if (pathLen != 1) revert BridgeFacet__reconcile_noPortalRouter();
    toDistribute = _reconcileProcessPortal(amount, token, routers[0], transferId);
  }

  if (pathLen != 0) {
    // fast liquidity path
    // Credit each router that provided liquidity their due 'share' of the asset.
    uint256 routerAmt = toDistribute / pathLen;
    for (uint256 i; i < pathLen; ) {
      s.routerBalances[routers[i]][token] += routerAmt;
      unchecked {
        i++;
      }
    }
  }

  emit Reconciled(transferId, _origin, routers, token, amount, msg.sender);
}
```

As you can see it uses amount in message to calculate what router should receive.  
This is `_handleExecuteLiquidity()` code which is used in `execute()`:
```solidity
function _handleExecuteLiquidity(
  bytes32 _transferId,
  bool _isFast,
  ExecuteArgs calldata _args
) private returns (uint256, address) {
  uint256 toSwap = _args.amount;

  // If this is a fast liquidity path, we should handle deducting from applicable routers' liquidity.
  // If this is a slow liquidity path, the transfer must have been reconciled (if we've reached this point),
  // and the funds would have been custodied in this contract. The exact custodied amount is untracked in state
  // (since the amount is hashed in the transfer ID itself) - thus, no updates are required.
  if (_isFast) {
    uint256 pathLen = _args.routers.length;

    // Calculate amount that routers will provide with the fast-liquidity fee deducted.
    toSwap = _getFastTransferAmount(_args.amount, s.LIQUIDITY_FEE_NUMERATOR, s.LIQUIDITY_FEE_DENOMINATOR);

    // Save the addressess of all routers providing liquidity for this transfer.
    s.routedTransfers[_transferId] = _args.routers;

    // If router does not have enough liquidity, try to use Aave Portals.
    // only one router should be responsible for taking on this credit risk, and it should only
    // deal with transfers expecting adopted assets (to avoid introducing runtime slippage)
    if (
      !_args.params.receiveLocal &&
      pathLen == 1 &&
      s.routerBalances[_args.routers[0]][_args.local] < toSwap &&
      s.aavePool != address(0)
    ) {
      if (!s.routerPermissionInfo.approvedForPortalRouters[_args.routers[0]])
        revert BridgeFacet__execute_notApprovedForPortals();

      // Portal provides the adopted asset so we early return here
      return _executePortalTransfer(_transferId, toSwap, _args.local, _args.routers[0]);
    } else {
      // for each router, assert they are approved, and deduct liquidity
      uint256 routerAmount = toSwap / pathLen;
      for (uint256 i; i < pathLen; ) {
        // decrement routers liquidity
        s.routerBalances[_args.routers[i]][_args.local] -= routerAmount;

        unchecked {
          i++;
        }
      }
    }
  }
}
```

As you can see it uses the amount defined in `ExecuteArgs` to see how much routers should pay.

Because of these two issues (deflationary tokens and swap slippage) attacker could fool protocol to spend more than what he transferred to protocol. This could be seen as two bugs.

## Recommendation

Update spending amount based on (deflationary tokens and swap slippage).

I think there is a misunderstanding here — the user takes on the slippage risk both into and out of the local assets, and the router has consistent returns on what was bridged.  

On `xcall`, the user swaps the amount put in for the local asset. This incurs some slippage, and only the amount of the local asset is bridged directly. It is the bridged amount that the router should supply liquidity for, and take fees on. Once the router supplies liquidity in `execute` (bridged amount minus the fees), then it is swapped for the local asset and sent to the user. The user may get some different amount here, but it is the user who is impacted by this slippage. On handle, the router is credited the bridged amount.  

However, there was a separate bug where the `transferId` was generated with the wrong `amount` on execute, so that could be where the confusion is coming from.

I actually agree with the warden here, it seems that they’re right about the issue but they just failed to mention the main reason why its an issue is because `transferId` is calculated using `_args.amount` which does not necessarily equal `bridgedAmt` due to slippage. Therefore, routers may end up fronting too much liquidity and receive considerably less when the bridge transfer is eventually reconciled. This seems rather severe as the user will receive the full transfer amount without slippage. This could be abused to drain routers on low liquidity tokens.

Right — I agree that the problems outlined here would be the true consequences for a mismatched `transferId`. If the question is to take the action outlined [here](https://github.com/code-423n4/2022-06-connext-findings/issues/227#issuecomment-1214224706) — specifically to keep this open and downgrade #227 as a QA — that would work with me.

**[LayneHaber (Connext) resolved](https://github.com/code-423n4/2022-06-connext-findings/issues/222):**

[connext/nxtp@f41a156](https://github.com/connext/nxtp/commit/f41a156b55a01837c8f57a77e52781f74406e1cd)

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates in the bridge contract’s handling of transfer amounts across the three phases of a cross‑chain transaction: the initial user call (xcall), the reconciliation of the received message (_reconcile), and the execution of fast‑liquidity routing (_handleExecuteLiquidity). When a user initiates a transfer, the contract records the amount the user signed in the XCallArgs structure ( _args.amount ) and uses this value to compute the transfer identifier (transferId). At the same time, the contract swaps the received asset to the local representation token, a step that can be affected by token‑level fees (deflationary tokens) or market slippage. The result of this swap, called bridgedAmt, is the amount that is actually sent across the Nomad bridge and later used in the reconciliation message. Because the transferId is derived from the original user‑signed amount rather than the bridgedAmt, the amount stored in the message and the amount that routers are expected to cover during fast‑liquidity execution can diverge. In the execute path, routers are required to provide liquidity equal to the user‑signed amount ( _args.amount ), which may be larger than the real bridged amount after slippage. During reconciliation, routers are reimbursed based on the smaller bridgedAmt, leaving them with a shortfall equal to the difference between the two values. An attacker can deliberately trigger this mismatch by using a deflationary token that burns a fraction on transfer, or by configuring a swap that incurs high slippage, thereby causing the bridgedAmt to be materially lower than the signed amount. The router therefore fronts more liquidity than it will ever receive back, potentially draining its balance after repeated attacks, especially on low‑liquidity assets. The issue is observable from a router’s perspective as a gradual reduction of its recorded balance despite seemingly successful transfers; users, however, receive the full amount they expect, which masks the problem. This mismatch is subtle because the protocol’s external events (XCalled and Reconciled) both report successful transfer amounts, and the discrepancy resides only in the internal accounting of router liquidity. The bug was discovered during a manual audit that traced the flow of amount variables through the bridge’s core functions and noticed that the transfer identifier and router settlement logic were based on different sources of truth. To remediate the issue, the contract should generate the transfer identifier from the actual bridged amount, adjust router accounting to credit them based on the amount they truly provided (the bridgedAmt), and incorporate explicit handling of token‑level fees and slippage tolerance when calculating router obligations. By aligning the amount used for transferId generation, reconciliation, and liquidity deduction, the protocol can ensure that routers are compensated fairly and that no unintended fund loss occurs.
