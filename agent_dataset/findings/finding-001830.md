---
id: 1830
severity: "High"
---

# Anyone can call VVVVCTokenDist

## Description

pepocpeter, plairfx, prgzro, redbeans, rsam_eth, shaflow01, udo, vladi319, whitehair0330, wildflowerzx, y4y  
Legitimate users can claim their reward with the ClaimParams signed by the signer. However, the VVVVCTokenDistribution::claim function just checks the validity of the signed params and doesn't check the caller is the right claimer. Hence anyone can claim the legitimate users' rewards by front-running the signed ClaimParams and because of the nonce increase legitimate users can't claim their reward.  
aaa66de349ef1b9e4bd331f14b/vvv-platform-smart-contracts/contracts/vc/VVVVCTokenDistributor.sol#L133  
Internal pre-conditions  
N/A  
External pre-conditions  
Legitimate users call claim function with signed params.  
Attack Path  
The VVVVCTokenDistribution::claim function is as follows:  
```solidity
function claim(ClaimParams memory _params) public {
    if (claimIsPaused) {
        revert ClaimIsPaused();
    }

    if (_params.projectTokenProxyWallets.length != _params.tokenAmountsToClaim.length) {
        revert ArrayLengthMismatch();
    }

    if (_params.nonce <= nonces[_params.kycAddress]) {
        revert InvalidNonce();
    }

    if (!_isSignatureValid(_params)) {
        revert InvalidSignature();
    }

    // update nonce
    nonces[_params.kycAddress] = _params.nonce;

    // define token to transfer
    IERC20 projectToken = IERC20(_params.projectTokenAddress);

    // transfer tokens from each wallet to the caller
    for (uint256 i = 0; i < _params.projectTokenProxyWallets.length; i++) {
        projectToken.safeTransferFrom(
            _params.projectTokenProxyWallets[i],
            msg.sender,
            _params.tokenAmountsToClaim[i]
        );
    }

    emit VCClaim(
        _params.kycAddress,
        _params.projectTokenAddress,
        _params.projectTokenProxyWallets,
        _params.tokenAmountsToClaim,
        _params.nonce
    );
}
```
At L119, the function checks the validity of the input params.  
The _isSignatureValid function is as follows:  
```solidity
function _isSignatureValid(ClaimParams memory _params) private view returns (bool) {
    bytes32 digest = keccak256(
        abi.encodePacked(
            "\x19\x01",
            DOMAIN_SEPARATOR,
            keccak256(
                abi.encode(
                    CLAIM_TYPEHASH,
                    _params.kycAddress,
                    _params.projectTokenAddress,
                    _params.projectTokenProxyWallets,
                    _params.tokenAmountsToClaim,
                    _params.nonce,
                    _params.deadline
                )
            )
        )
    );

    address recoveredAddress = ECDSA.recover(digest, _params.signature);

    bool isSigner = recoveredAddress == signer;
    bool isExpired = block.timestamp > _params.deadline;
    return isSigner && !isExpired;
}
```
The function just checks if the signature is signed by the signer. The VVVVCTokenDistribution::claim function doesn't check if the msg.sender is the kycAddress and this leads to anyone can claim legitimate kycAddress reward by front-running the params. Besides at L124, it increases the nonce of the kycAddress to prevent the double claim, hence the legitimate claimer can't claim their rewards.  
Though, front-running may be hard on L2 but this leads to loss of fund to users and it will be deployed on Ethereum also.  
Anyone can claim other legitimate users' rewards and the legitimate users can't claim their rewards.

## Proof of Concept

no poc

## Recommendation

It is recommended to send the reward to the kycAddress not the msg.sender.  
```solidity
function claim(ClaimParams memory _params) public {
    if (claimIsPaused) {
        revert ClaimIsPaused();
    }
    if (_params.projectTokenProxyWallets.length != _params.tokenAmountsToClaim.length) {
        revert ArrayLengthMismatch();
    }
    if (_params.nonce <= nonces[_params.kycAddress]) {
        revert InvalidNonce();
    }
    if (!_isSignatureValid(_params)) {
        revert InvalidSignature();
    }
    // update nonce
    nonces[_params.kycAddress] = _params.nonce;
    // define token to transfer
    IERC20 projectToken = IERC20(_params.projectTokenAddress);
    // transfer tokens from each wallet to the caller
    for (uint256 i = 0; i < _params.projectTokenProxyWallets.length; i++) {
        projectToken.safeTransferFrom(
            _params.projectTokenProxyWallets[i],
            _params.kycAddress,
            _params.tokenAmountsToClaim[i]
        );
    }
    emit VCClaim(
        _params.kycAddress,
        _params.projectTokenAddress,
        _params.projectTokenProxyWallets,
        _params.tokenAmountsToClaim,
        _params.nonce
    );
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an authorization flaw in the token distribution contract where the claim function validates a signed ClaimParams structure but does not verify that the caller (msg.sender) matches the KYC address that is authorized to receive the reward. The root cause is the missing check that binds the signed parameters to the intended recipient, allowing any external account to submit a valid claim with the same signed data. An attacker can observe a legitimate user’s signed claim parameters, submit a transaction that calls claim before the user does (front‑running), and because the contract transfers the tokens to msg.sender, the attacker receives the full reward. After the transfer, the contract updates the nonce for the KYC address, which prevents the original user from submitting a second claim with the same nonce, effectively locking out the rightful recipient. This issue manifests whenever a user attempts to claim rewards using a signed message; the contract will accept the signature, update the nonce, and send the tokens to whoever called the function. The affected parties are the legitimate token recipients, the protocol’s users, and any downstream applications that rely on correct reward distribution. The flaw was discovered during a manual audit that compared the signature verification logic with the token transfer destination and noticed the absence of a sender‑to‑recipient check. Because the contract appears to work correctly from a signature perspective, the problem can be subtle and may not be evident until a user reports missing funds. The impact is a loss of tokens for honest users and a potential drain of the distribution pool if attackers repeatedly front‑run claims. Conceptually, the bug belongs to the class of improper authentication or missing access control, where a function trusts data without confirming the caller’s identity. To remediate, the contract should transfer the tokens to the KYC address specified in the signed parameters rather than to msg.sender, or it should explicitly require that msg.sender equals the KYC address before proceeding. This change restores the intended business logic that rewards are delivered to the verified recipient and prevents unauthorized parties from hijacking the claim process.
